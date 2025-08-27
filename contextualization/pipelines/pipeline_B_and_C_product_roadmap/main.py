import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import pandas as pd
from dateutil import parser as dateutil_parser
from opentelemetry.trace import get_current_span
from otel_extensions import instrumented
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from contextualization.conf.config import conf, llm_name
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.acceleration_summary import (
    generate_acceleration_summary,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.delivery_estimates import (
    append_git_delivery_estimates,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.extract_git_initiatives import (
    analyze_git_commits,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.end_date_insights_prompt import (
    end_date_insights_chain,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.recommendation_insight_prompt import (
    recommendation_insight_chain,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.reconciliation_insights_prompt import (
    insights_chain,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.summary_prompt import (
    summary_chain,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.topic_extract_prompt import (
    chain_topic_assign_git,
    chain_topic_assign_to_jira_from_git,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import (
    GitInitiatives,
    PipelineBCResult,
    PipelineBCResultItem,
)
from contextualization.tools.json_tools import round_percentages
from contextualization.tools.llm_tools import (
    calculate_token_count_async,
    get_batches,
)
from contextualization.utils.csv_loader import load_csv_safely
from contextualization.utils.parse_jira_fields import parse_changelog_data
from contextualization.utils.vcr_mocks import calls_context

logger = logging.getLogger(__name__)


token_limit = conf["llms"][llm_name]["token_limit"]
batch_threshold = conf["llms"][llm_name]["batch_threshold"]


@instrumented
async def git_topic_assign_to_git_data(
    df_lists: list[pd.DataFrame],
    topics: dict[str, list[dict[str, str]]],
    task: str,
    output_path: Path,
    error_log_path: Path,
) -> pd.DataFrame:
    result = ""
    if "initiatives" in topics:
        for index, topic_dict in enumerate(topics["initiatives"], 1):
            # Add a numbered topic
            result += f"{index}. Topic: {topic_dict['initiative_name']}\n"

            # Add description with "Description:" prefix
            result += f"   Description: {topic_dict['initiative_description']}\n\n"

    # Check if a result is empty after processing
    if not result.strip():  # strip() to remove any extra whitespace
        raise ValueError("No valid topics found to process in 'initiatives'. The result is empty.")

    async def analyze_change_with_token_callback(batch_content: list[str]) -> list[Any]:
        try:
            logger.info("Assigning Git initiatives to the current batch of Git data...")
            outputs = await chain_topic_assign_git.abatch(
                [
                    {
                        "diff_summary": file_content,
                        "topic": result,
                        "task": task,
                    }
                    for file_content in batch_content
                ]
            )

            logger.info(
                f"Successfully assigned Git initiatives to records of git data.",
                extra={
                    "batches_type": "git_initiatives_git_data",
                },
            )
            return outputs

        except Exception:
            logger.exception("Pipeline B/C - Error processing batch")
            return [None] * len(batch_content)

    batch_number = 0
    try:
        # Process the DataFrame in batches
        for batch in df_lists:
            batch_number += 1
            batch_size = len(batch)
            logger.info(f"Processing Batch {batch_number} with size {batch_size}...")

            # Ensure the 'Summary' column exists
            if "Summary" not in batch.columns:
                raise ValueError("The DataFrame must contain a 'Summary' column.")

            # Apply the analysis to each entry in the batch
            batch_results = await analyze_change_with_token_callback(batch["Summary"].tolist())

            process_batch_results(batch, batch_results, batch_number, output_path, error_log_path)

    except Exception:
        logger.exception("Pipeline B/C - Error occurred while assigning git initiatives to git data batches")

    # Load and return the full, saved DataFrame with original and new columns
    if os.path.exists(output_path):
        return load_csv_safely(output_path)
    else:
        raise FileNotFoundError(f"The file '{output_path}' does not exist.")


async def project_exists(
    jira_url: str,
    project_key: str,
    user: str | None,
    confluence_token: str | None,
    start_date: str,
    end_date: str,
    jira_access_token: str | None = None,
) -> bool:
    """
    Check if a project exists in Jira.
    """

    jql_query = f'project="{project_key}" AND created >= "{start_date}" AND created <= "{end_date}"'
    api_url = f"{jira_url}/rest/api/2/search?jql={quote(jql_query)}&maxResults=10&expand=changelog"

    headers = {"Accept": "application/json"}
    client = httpx.AsyncClient()
    if jira_access_token:
        headers["Authorization"] = f"Bearer {jira_access_token}"
        response = await client.get(api_url, headers=headers)
    else:
        response = await client.get(api_url, auth=(user, confluence_token), headers=headers)

    if response.status_code != 200:
        logger.warning(
            f"No project found with key",
            extra={"project_key": project_key, "jira_url": jira_url},
        )
        return False
    else:
        return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=60, max=60 * 3),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def _fetch_data_jira_api(
    client: httpx.AsyncClient,
    api_url: str,
    jira_access_token: str | None = None,
    user: str | None = None,
    confluence_token: str | None = None,
):
    headers = {"Accept": "application/json"}
    if jira_access_token:
        headers["Authorization"] = f"Bearer {jira_access_token}"
        response = await client.get(api_url, headers=headers)
    else:
        response = await client.get(api_url, auth=(user, confluence_token), headers=headers)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        if response.status_code == 400:
            logger.exception(
                "JIRA API returned 400 (Bad Request). Possibly due to malformed JQL or empty project list.",
                extra={
                    "response_status": response.status_code,
                    "response_text": response.text,
                    "api_url": api_url,
                },
            )
            return None

        raise

    return response.json()


@instrumented
async def get_jira_data_contextualization(
    jira_url: str,
    project_names: list[str],
    user: str | None,
    confluence_token: str | None,
    start_date: str,
    end_date: str,
    jira_access_token: str | None = None,
) -> pd.DataFrame:
    try:
        as_of_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        max_results = 100
        start_at = 0
        total_issues = []

        fields_to_fetch = "key,summary,description,issues,status,issuetype,priority,assignee,created,updated,priority,components,labels,attachment,issuelinks"

        # Project names list - only of projects that exist
        project_names_that_exist = []
        for project in project_names:
            if await project_exists(
                jira_url,
                project,
                user,
                confluence_token,
                start_date,
                end_date,
                jira_access_token,
            ):
                project_names_that_exist.append(project)

        if not project_names_that_exist:
            logger.info("No valid JIRA projects found. Skipping JIRA data fetch.")
            return pd.DataFrame()

        project_list = ",".join([f'"{p}"' for p in project_names_that_exist])
        client = httpx.AsyncClient(timeout=30)

        while True:
            # Ensures proper quoting
            jql_query = f"""project IN ({project_list})
                AND (
                    status CHANGED DURING ("{start_date}", "{end_date}")
                    OR (status IN ("IN PROGRESS", "TO DO") AND updated >= "{start_date}" AND updated <= "{end_date}")
                    OR (created >= "{start_date}" AND created <= "{end_date}")
                )"""

            api_url = (
                f"{jira_url}/rest/api/2/search?"
                f"jql={quote(jql_query)}"
                f"&fields={fields_to_fetch}"
                f"&maxResults={max_results}&startAt={start_at}&expand=changelog"
            )
            data = await _fetch_data_jira_api(client, api_url, jira_access_token, user, confluence_token)
            if data is None:
                return pd.DataFrame()

            for issue in data.get("issues", []):
                updated_date = dateutil_parser.parse(issue["fields"].get("updated", "")).date()

                if updated_date >= as_of_date and issue["fields"].get("status", {}).get("name") not in [
                    "Opportunity",
                    "Intro",
                    "Closed Lost",
                ]:
                    total_issues.append(issue)

            if data["startAt"] + len(data["issues"]) >= data["total"]:
                break

            start_at += max_results  # Increment pagination

        logger.info(
            f"Total amount of issues fetched: {len(total_issues)}",
            extra={"issues_count": len(total_issues)},
        )
        df = pd.DataFrame(
            {
                "issue_key": [issue["key"] for issue in total_issues],
                "Fields": [issue["fields"] for issue in total_issues],
                "changelog": [issue["changelog"] for issue in total_issues],
            }
        )
        return df

    except Exception:
        """
        Just logging the exception and not re-raising here because the pipeline should
        continue on GIT data even if the JIRA data is not fetched successfully or is absent.
        """
        logger.exception("Error occurred while fetching JIRA data using JIRA API")
        return pd.DataFrame()


@instrumented
async def process_jira_data(
    jira_url: str,
    project_names: list[str],
    confluence_user: str | None,
    confluence_token: str | None,
    start_date: str,
    end_date: str,
    jira_access_token: str | None = None,
) -> pd.DataFrame:
    """
    Process JIRA data and return a cleaned DataFrame with important columns.
    """
    try:
        df = await get_jira_data_contextualization(
            jira_url,
            project_names,
            confluence_user,
            confluence_token,
            start_date,
            end_date,
            jira_access_token,
        )

        get_current_span().set_attribute("ticket_count", len(df))

        if df.empty:
            logger.warning("No tickets data returned by Jira API")
            return df

        # Normalize fields
        df_fields = pd.json_normalize(df["Fields"], max_level=0)
        df = df.drop(columns=["Fields"]).join(df_fields)

        # Remove custom fields
        df = df.loc[:, ~df.columns.str.startswith("customfield")]

        # Select important columns
        important_columns = [
            "issue_key",
            "issuetype",
            "summary",
            "status",
            "priority",
            "assignee",
            "created",
            "updated",
            "description",
            "changelog",
            "components",
            "labels",
            "attachment",
            "issuelinks",
        ]
        df = df[df.columns.intersection(important_columns)]

        # Process columns safely
        df["status"] = df["status"].apply(lambda x: (x.get("name") if isinstance(x, dict) else None))
        df["assignee"] = df["assignee"].apply(lambda x: x.get("displayName") if isinstance(x, dict) else None)
        df["priority"] = df["priority"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
        df["issuetype"] = df["issuetype"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)

        # Rename columns
        df.rename(columns={"issuetype": "Issue Type"}, inplace=True)
        df["description"] = df["description"].fillna(df["summary"])

        # Apply the parse function changelog column
        df["parsed_changelog"] = df["changelog"].apply(parse_changelog_data)

        # Filter to handle timezone issue
        df["timezone_independent_created_date"] = pd.to_datetime(
            df["created"].str.split("T").str[0], errors="coerce"
        ).dt.date
        df["timezone_independent_updated_date"] = pd.to_datetime(
            df["updated"].str.split("T").str[0], errors="coerce"
        ).dt.date
        start_date_filter = pd.to_datetime(start_date).date()
        end_date_filter = pd.to_datetime(end_date).date()
        timezone_filtered_df = df[
            (
                (df["timezone_independent_created_date"] >= start_date_filter)
                & (df["timezone_independent_created_date"] <= end_date_filter)
            )
            | (
                (df["timezone_independent_updated_date"] >= start_date_filter)
                & (df["timezone_independent_updated_date"] <= end_date_filter)
            )
        ]

        return timezone_filtered_df
    except Exception:
        logger.exception("Pipeline B/C - Error occurred while processing JIRA data")
        return pd.DataFrame()


@instrumented
async def git_topic_assign_to_jira_data(
    df_lists: list[pd.DataFrame],
    topics: dict[str, list[dict[str, str]]],
    task: str,
    output_path: Path,
    error_log_path: Path,
) -> pd.DataFrame:
    result = ""
    if "initiatives" in topics:
        for index, topic_dict in enumerate(topics["initiatives"], 1):
            # Add a numbered topic
            result += f"{index}. Topic: {topic_dict['initiative_name']}\n"

            # Add description with "Description:" prefix
            result += f"   Description: {topic_dict['initiative_description']}\n\n"

    # Check if a result is empty after processing
    if not result.strip():  # strip() to remove any extra whitespace
        raise ValueError("No valid initiatives found to process in 'initiatives'. The result is empty.")

    async def analyze_change_with_token_callback(batch_content: list[str]) -> list[Any]:
        try:
            logger.info("Assigning Git initiatives to the current batch of Jira data...")
            outputs = await chain_topic_assign_to_jira_from_git.abatch(
                [
                    {
                        "jira_description": file_content,
                        "topic": result,
                        "task": task,
                    }
                    for file_content in batch_content
                ]
            )
            logger.info(
                f"Successfully assigned Git initiatives to records of jira data.",
                extra={
                    "batches_type": "git_initiatives_jira_data",
                },
            )
            return outputs

        except Exception:
            logger.exception("Pipeline B/C - Error processing batch")
            return [None] * len(batch_content)

    batch_number = 0
    try:
        # Process the DataFrame in batches
        for batch in df_lists:
            batch_number += 1
            batch_size = len(batch)
            logger.info(f"Processing Batch {batch_number} with size {batch_size}...")
            # Ensure the 'Summary' column exists
            if "description" not in batch.columns:
                raise ValueError("The DataFrame must contain a 'description' column.")

            # Apply the analysis to each entry in the batch with
            batch_results = await analyze_change_with_token_callback(batch["description"].tolist())

            process_batch_results(batch, batch_results, batch_number, output_path, error_log_path)

    except Exception:
        logger.exception("Pipeline B/C - Error occurred while assigning git initiatives to jira data batches")

    # Load and return the full, saved DataFrame with original and new columns
    if os.path.exists(output_path):
        return load_csv_safely(output_path)
    else:
        raise FileNotFoundError(f"The file '{output_path}' does not exist.")


def process_batch_results(
    batch: pd.DataFrame,
    batch_results: list[Any],
    batch_number: int,
    output_path: Path,
    error_log_path: Path,
) -> None:
    """
    Process batch results by separating successful and errored results,
    writing successful results to output CSV and errors to error log CSV.
    """

    batch_results_series = pd.Series(batch_results)

    success_results = [res for res in batch_results if res is not None]
    logger.info(f"Length of successful results obtained for batch {batch_number}: {len(success_results)}")
    error_indices = batch.index[batch_results_series.isna()]

    if success_results:
        success_df = pd.DataFrame(success_results, index=batch.index[: len(success_results)])
        updated_batch = batch.merge(success_df, left_index=True, right_index=True)
        updated_batch.to_csv(
            output_path,
            mode="a",
            header=not os.path.exists(output_path),
            index=False,
        )

    if not error_indices.empty:
        error_records = batch.loc[error_indices]

        error_records.to_csv(
            error_log_path,
            mode="a",
            index=False,
            header=not os.path.exists(error_log_path),
        )


def update_changes_with_percentages(
    df: pd.DataFrame,
    data: dict[str, Any],
    column_name: str,
) -> dict[str, Any]:
    """
    Updates the 'initiatives' key in the provided JSON-like dictionary `data`
    with the percentages of each category from the DataFrame `df`.
    """
    logger.info("Updating the percentage with actual percentages of git initiatives.")
    try:
        # Calculate category percentages
        category_counts = df[column_name].value_counts()
        total_count = len(df)
        category_percentage = round((category_counts / total_count) * 100, 2)

        # Convert to dictionary
        category_percentage_dict = category_percentage.to_dict()

        # Update JSON with calculated percentages, ensuring missing ones are set to 0%
        for change in data.get("initiatives", []):
            if "initiative_name" in change:
                category_name = change["initiative_name"]
                change["initiative_percentage"] = category_percentage_dict.get(
                    category_name, 0
                )  # Default to 0 if not found

        return data

    except Exception:
        logger.exception(
            f"Pipeline B/C - Error while updating the percentage with actual percentages for git initiatives"
        )
        return data


def add_jira_initiative_completion_percentage(
    data: dict[str, Any],
    jira_data: pd.DataFrame,
    end_date_dict: dict[str, Any],
    initiative_column_label: str,
) -> dict[str, Any]:
    """
    Updates the 'initiatives' key in the provided JSON-like dictionary `data`
    with the percentages of each category from the Jira data.
    """
    logger.info("Updating the completion percentage for each initiative")

    try:
        # Read Jira data
        jira_data.columns = jira_data.columns.str.strip()
        jira_data["status"] = jira_data["status"].astype(str).str.strip()
        jira_data[initiative_column_label] = jira_data[initiative_column_label].astype(str).str.strip()

        # Calculate 'Done' percentages
        done_count = jira_data[jira_data["status"] == "Done"].groupby(initiative_column_label).size()
        total_count = jira_data.groupby(initiative_column_label).size()
        percentage_done = (done_count / total_count * 100).fillna(0)

        # Convert to dictionary
        percentage_done_dict = percentage_done.to_dict()
        done_count_dict = done_count.to_dict()
        total_count_dict = total_count.to_dict()
        logger.info(f"Got percentages of initiatives: {percentage_done_dict}")

        # Ensure all initiatives in `data["initiatives"]` are updated, including missing ones
        for change in data.get("initiatives", []):
            if "initiative_name" in change:
                category_name = change["initiative_name"]
                change["percentage_tickets_done"] = percentage_done_dict.get(
                    category_name, 0
                )  # Default to 0 if not found
                change["number_ticket_done"] = done_count_dict.get(category_name, 0)  # Default to 0 if not found
                change["total_tickets"] = total_count_dict.get(category_name, 0)  # Default to 0 if not found
                change["estimated_end_date"] = end_date_dict.get(category_name, 0)  # Default to 0 if not found

        logger.info("Updated the completion percentage for each initiative")

        return data

    except Exception as e:
        logger.exception(f"Pipeline B/C - Error while updating the completion percentage of initiatives")
        return data  # Return the original data even in case of an error


@instrumented
async def add_summary(input_data: dict[str, Any], file_path: Path) -> dict[str, Any] | None:
    """
    Reads a JSON file, processes its data using the summary chain, and updates the file.
    """
    logger.info("Updating the git initiative json with summary.")
    try:
        # Validate the JSON structure
        if not isinstance(input_data, dict):
            raise TypeError("JSON file content must be a dictionary.")

        # Process the data
        response = await summary_chain.ainvoke({"input_json": input_data})

        # Update the data and write it back to the file
        input_data.update(response)
        with open(file_path, "w") as file:  # Directly open in 'w' mode for overwriting
            json.dump(input_data, file, indent=4)

        logger.info("Updated the git initiative json with summary.")

        return input_data

    except Exception:
        logger.exception(f"Pipeline B/C - An error occurred while updating the git initiative json with summary")


def add_start_date(
    data: pd.DataFrame,
    json_data: dict[str, Any],
    output_csv: Path,
    initiative_column_label: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """
    Adds the earliest 'start_date' for each initiative in the given DataFrame.
    """
    updated_data = None
    try:
        # Ensure the 'created' column is in datetime format, dropping invalid values
        data["created"] = pd.to_datetime(data["created"], errors="coerce")
        data = data.dropna(subset=["created"])  # Remove rows where 'created' is NaN

        # Get the earliest 'created' date for each initiative
        earliest_dates = data.groupby(initiative_column_label)["created"].min().reset_index()
        earliest_dates.rename(columns={"created": "start_date"}, inplace=True)

        # Keep only the date (YYYY-MM-DD) without time
        earliest_dates["start_date"] = pd.to_datetime(earliest_dates["start_date"], utc=True)
        earliest_dates["start_date"] = earliest_dates["start_date"].dt.date

        # Merge start_date into the original DataFrame
        updated_data = data.merge(earliest_dates, on=initiative_column_label, how="left")

        # Save updated DataFrame to CSV
        updated_data.to_csv(output_csv, index=False)
        logger.info(f"'start_date' column added to Jira data and saved to {output_csv}")

        # Convert to dictionary for an easy lookup
        start_date_dict = dict(
            zip(
                earliest_dates[initiative_column_label],
                earliest_dates["start_date"],
            )
        )

        # Add 'start_date' to JSON
        for change in json_data.get("initiatives", []):  # Use .get() to prevent KeyError
            initiative_name = change.get("initiative_name")
            start_date_value = start_date_dict.get(initiative_name)
            change["start_date"] = str(start_date_value) if start_date_value is not None else None

        logger.info(f"'start_date' added to initiatives successfully")

    except Exception:
        logger.exception(f"Pipeline B/C - An error occurred while adding the start_date")

    return json_data, updated_data


def delete_existing_files(*file_paths: Path) -> None:
    """Delete specified files if they exist."""
    for file_path in file_paths:
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"Deleted existing file: {file_path}")


@instrumented
def get_estimated_end_date(
    jira_data: pd.DataFrame, initiative_column_label: str, jira_data_path: Path
) -> dict[str, Any]:
    """
    Takes jira data as input and returns a dictionary with initiatives and their end date estimates.
    """
    logger.info(f"calculating estimated end date")
    done_status = jira_data[jira_data["status"] == "Done"]
    if done_status.shape[0] == 0:
        return {}

    filepath = jira_data_path / "original_jira_data.json"
    with open(filepath, "w") as f:
        json.dump(done_status.to_dict(), f, indent=4)

    logger.info(f"original jira data saved to {filepath}")

    def parse_jira_datetime(timestamp: str) -> datetime:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")

    # Extract the time difference between "In Progress" to "Done"
    def calculate_status_time_difference(changelog: list[dict[str, Any]]) -> tuple[float | str, datetime | str]:
        """
        This function calculates the start and end date from jira data.
        This function tries to fetch the start date of a ticket in 2 ways:
            1. If in the jira extracted history we get the date when the task was changed
             to inprogress, we take that date
            2. If we do not find the task string in-progress, then we make the created date as in-progress
        This function try to fetch the done date when the task string in jira data is marked as done
        This function then calculate the difference in hours by done date - in progress date
        """
        try:
            in_progress_time = None
            done_time = None

            for log in changelog:
                created_time = parse_jira_datetime(log["created"])
                for item in log["items"]:
                    if item["field"] == "status":
                        if (
                            (
                                item.get("fromString") == "In Progress"
                                and item.get("toString") == "Done"
                                and done_time is None
                            )
                            or item.get("toString") == "Done"
                            and done_time is None
                        ):
                            done_time = created_time
                        elif item.get("toString") == "In Progress":
                            in_progress_time = created_time
            if not in_progress_time:
                in_progress_time = created_time

            if in_progress_time and done_time:
                return (done_time - in_progress_time).total_seconds() / 3600, done_time  # Hours
            return "cannot calculate", "cannot calculate"
        except Exception as e:
            logger.exception(f"Pipeline B/C - An error occurred while adding the start_date")
            return "cannot calculate", "cannot calculate"

    done_status["changelog"] = done_status["changelog"].apply(lambda x: eval(x))
    done_status[["completed_time", "done_date"]] = (
        done_status["changelog"].apply(lambda x: calculate_status_time_difference(x["histories"])).apply(pd.Series)
    )
    logger.info(f"calculating the average time take by task per initiative to complete")
    # Convert 'completed_time' to numeric, setting errors='coerce' to ignore strings
    done_status["completed_time"] = pd.to_numeric(done_status["completed_time"], errors="coerce")

    # Drop rows where 'completed_time' is NaN (caused by conversion errors)
    done_status = done_status.dropna(subset=["completed_time"])
    avg_done_time_for_category = (
        done_status.groupby(initiative_column_label).agg({"completed_time": "mean"}).reset_index()
    )

    logger.info(f"calculating the maximum done date for every initiatve")
    ## this will be used if the initiative is 100% completed the estimated date will be the max done date.
    # Convert 'completed_time' to numeric, setting errors='coerce' to ignore strings
    done_status["done_date"] = pd.to_datetime(done_status["done_date"], errors="coerce")
    # Drop rows where 'completed_time' is NaN (caused by conversion errors)
    done_status = done_status.dropna(subset=["done_date"])
    max_done_date_for_initiative = done_status.groupby(initiative_column_label).agg({"done_date": "max"}).reset_index()
    filtered_df = jira_data[jira_data["status"] != "Done"]
    # Group by category and count tickets
    category_counts = (
        filtered_df.groupby(initiative_column_label).agg(ticket_count=(initiative_column_label, "count")).reset_index()
    )
    # merging the df for time,max date, count of tickets per initiative
    count_df = avg_done_time_for_category.merge(
        category_counts, on=initiative_column_label, how="left"
    ).merge(  # First merge
        max_done_date_for_initiative, on=initiative_column_label, how="left"
    )  # Second merge
    count_df.fillna({"ticket_count": 0}, inplace=True)

    def calculate_total_time(row: pd.Series) -> float | str:
        try:
            return row["completed_time"] * row["ticket_count"]
        except Exception:
            return "cannot be calculated"

    # Apply the function row-wise
    count_df["total_time_remaining"] = count_df.apply(calculate_total_time, axis=1)

    def add_hours_to_date(row: pd.Series) -> datetime.date:
        today = datetime.now()
        updated_date = today + timedelta(hours=row["total_time_remaining"])  # Add hours
        if row["ticket_count"] < 1:
            return row["done_date"].date()
        else:
            return updated_date.date()

    # this will calculate the estimated time if the task is not 100% done and if 100%
    # then return the max date.

    if count_df.empty:
        logger.info("Analysis data is empty, fallback to empty return")
        return {}

    count_df["estimated_end_date"] = count_df.apply(add_hours_to_date, axis=1).astype(str)
    category_end_date = dict(
        zip(
            count_df[initiative_column_label],
            count_df["estimated_end_date"],
        )
    )

    return category_end_date


async def add_estimated_end_date_insights(input_data: dict[str, Any]) -> dict[str, Any]:
    logger.info("Adding estimated end date insights to initiatives.")

    initiatives = input_data["initiatives"]
    if not initiatives:
        logger.info("No initiatives to process.")
        return input_data

    batch_inputs = []
    initiative_mappings = []

    for idx, change in enumerate(initiatives):
        if not change["estimated_end_date"]:
            change["estimated_end_date_insights"] = "No estimated end date available."
        else:
            try:
                average_time_per_ticket = (
                    datetime.strptime(change["estimated_end_date"], "%Y-%m-%d")
                    - datetime.strptime(change["start_date"], "%Y-%m-%d")
                ).days / change["total_tickets"]
            except ValueError:
                average_time_per_ticket = 0

            total_tickets = change["total_tickets"]
            estimated_total_time = total_tickets * average_time_per_ticket

            batch_inputs.append(
                {
                    "input_json": change,
                    "average_time_per_ticket": average_time_per_ticket,
                    "total_tickets": total_tickets,
                    "estimated_total_time": estimated_total_time,
                }
            )
            initiative_mappings.append(idx)

    if batch_inputs:
        logger.info(f"Processing {len(batch_inputs)} initiatives with LLM batch processing...")
        try:
            end_date_insights = await end_date_insights_chain.abatch(batch_inputs)

            for insight_result, initiative_idx in zip(end_date_insights, initiative_mappings):
                initiatives[initiative_idx]["estimated_end_date_insights"] = insight_result

        except Exception:
            logger.exception("Error processing end date insights batch")
            for initiative_idx in initiative_mappings:
                initiatives[initiative_idx]["estimated_end_date_insights"] = "Error generating end date insights."

    input_data["initiatives"] = initiatives
    logger.info("Updated the initiatives with estimated end date insights.")

    return input_data


def normalize_epics_percentage(initiatives_json: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes epic percentages within each initiative based on its total percentage.
    """

    try:
        for initiative in initiatives_json.get("initiatives", []):
            # Calculate the total epic percentage within an initiative
            total_epic_percentage = sum(epic.get("epic_percentage", 0) for epic in initiative.get("epics", []))

            if total_epic_percentage == 0:
                logger.warning(
                    f"Total epic percentage is zero for initiative: {initiative.get('initiative_name', 'Unknown')}"
                )
                continue

            # Normalize each epic's percentage based on the initiative's percentage
            for epic in initiative.get("epics", []):
                original_percentage = epic.get("epic_percentage", 0)
                normalized_percentage = (original_percentage / total_epic_percentage) * initiative.get(
                    "initiative_percentage", 0
                )
                epic["epic_percentage"] = normalized_percentage
                logger.info(f"Updated epic percentage for epic {epic['epic_name']}: {normalized_percentage:.2f}")

        return initiatives_json

    except Exception as e:
        logger.exception(f"Pipeline B/C - Error normalizing epic percentages")
        return initiatives_json


@instrumented
async def reconciliation_insights(git_initiatives: dict[str, Any], insights_path: str | Path) -> list[Any]:
    insights = []
    try:
        insights = await insights_chain.ainvoke({"git_initiatives": git_initiatives})
        logger.info(f"Extracted the reconciliation insights from the data.")

        # Store the insights into json file
        with open(insights_path, "w") as file:
            json.dump(insights, file, indent=4)
        logger.info(f"Successfully stored the reconciliation insights at {insights_path}")
    except Exception as e:
        logger.exception(f"Pipeline B/C - An error occurred while generating the reconciliation insights")
    return insights


@instrumented
async def add_expedited_date_recommendation_insights(
    initiatives: dict[str, Any], initiative_path: Path, today_date: datetime
) -> dict[str, Any]:
    """
    Load initiatives from a JSON file, generate recommendation insights, and update the initiatives.
    """
    try:
        current_date = today_date.date().isoformat()

        # Prepare batch inputs for initiatives that need LLM processing
        batch_inputs = []
        initiative_mappings = []

        logger.info(f"Generating the expedited date recommendation insights..")
        for idx, initiative in enumerate(initiatives.get("initiatives", [])):
            batch_inputs.append({"initiative": initiative, "current_date": current_date})
            initiative_mappings.append(idx)

        # Process all LLM requests in one batch
        if batch_inputs:
            try:
                recommendation_insights = await recommendation_insight_chain.abatch(batch_inputs)

                # Update initiatives with the generated insights
                for idx, recommendation_insight in zip(initiative_mappings, recommendation_insights):
                    initiatives["initiatives"][idx].update(recommendation_insight)

            except Exception:
                logger.exception(f"Pipeline B/C - Error processing batch recommendations")

        # Save the updated initiatives back to the file
        with open(initiative_path, "w") as file:
            json.dump(initiatives, file, indent=4)
        logger.info(f"Updated initiatives with recommendation insights saved to: {initiative_path}")

    except Exception:
        logger.exception(f"Pipeline B/C - An error occurred while generating the recommendation insights")

    return initiatives


async def main(
    today_date: datetime,
    chat_input: str | None = None,
    jira_data_df: pd.DataFrame | None = None,
    git_data_with_summary_df: pd.DataFrame | None = None,
    git_data_summary_csv_path: Path | None = None,
) -> PipelineBCResultItem:
    # Load git data
    logger.info(f"Git data loaded with shape: {git_data_with_summary_df.shape}")

    git_data_summary_csv_path = Path(git_data_summary_csv_path)

    # Define directories for outputs
    base_output_dir = git_data_summary_csv_path.parent
    jira_only_dir = base_output_dir / "jira_data"
    git_only_dir = base_output_dir / "git_data_only"
    jira_and_git_dir = base_output_dir / "jira_and_git"

    # Create directories if they don't exist
    jira_only_dir.mkdir(parents=True, exist_ok=True)
    git_only_dir.mkdir(parents=True, exist_ok=True)
    jira_and_git_dir.mkdir(parents=True, exist_ok=True)

    if jira_data_df is not None and not jira_data_df.empty:
        # Define file paths

        output_path_for_jira = jira_only_dir / f"{git_data_summary_csv_path.stem}_jira_data_with_jira_initiatives.csv"
        error_log_path_for_jira = (
            jira_only_dir / f"{git_data_summary_csv_path.stem}_jira_data_with_jira_initiatives_error_data.csv"
        )
        output_path_jira = jira_and_git_dir / f"{git_data_summary_csv_path.stem}_git_data_with_jira_initiatives.csv"
        error_log_path_jira = (
            jira_and_git_dir / f"{git_data_summary_csv_path.stem}_git_data_with_jira_initiatives_error_data.csv"
        )
        output_path_git = jira_and_git_dir / f"{git_data_summary_csv_path.stem}_git_data_with_jira_git_initiatives.csv"
        error_log_path_git = (
            jira_and_git_dir / f"{git_data_summary_csv_path.stem}_git_data_with_jira_git_error_data.csv"
        )

        # Delete existing files before rerun
        delete_existing_files(
            output_path_for_jira,
            error_log_path_for_jira,
            output_path_jira,
            error_log_path_jira,
            output_path_git,
            error_log_path_git,
        )
    else:
        output_path_git = git_only_dir / f"{git_data_summary_csv_path.stem}_git_data_with_initiatives.csv"
        error_log_path_git = git_only_dir / f"{git_data_summary_csv_path.stem}_git_error_data.csv"

        # Delete existing files before rerun
        delete_existing_files(
            output_path_git,
            error_log_path_git,
        )

    # Task description
    task = "Assign the topics based on provided Summary."

    # Calculate token count
    git_data = await calculate_token_count_async(git_data_with_summary_df)

    # Process Git initiatives
    git_initiatives, git_initiatives_path = await analyze_git_commits(
        git_data_summary_csv_path, git_data_with_summary_df, chat_input
    )

    # Assign initiatives to Git data
    batches_of_df_git = get_batches(git_data, tiktoken_column="summary_tik_token")

    # Assign Git initiatives to git data
    output_data_git = await git_topic_assign_to_git_data(
        batches_of_df_git,
        git_initiatives,
        task,
        output_path_git,
        error_log_path_git,
    )

    git_updated_initiatives = update_changes_with_percentages(
        output_data_git, git_initiatives, column_name="Categorization_of_initiative_git"
    )

    jira_df = None
    if jira_data_df is not None and not jira_data_df.empty:  # If Jira data is available
        output_path_for_jira_git_initiatives = (
            jira_and_git_dir / f"{git_data_summary_csv_path.stem}_jira_data_with_git_initiatives.csv"
        )
        error_log_path_for_jira_git_initiatives = (
            jira_and_git_dir / f"{git_data_summary_csv_path.stem}_jira_data_with_git_initiatives_error_data.csv"
        )

        # Path to store the results reconciliation insights
        insights_path = (
            git_data_summary_csv_path.parent / f"{git_data_summary_csv_path.stem}_reconciliation_insights.json"
        )

        # Delete existing files before rerun
        delete_existing_files(
            output_path_for_jira_git_initiatives,
            error_log_path_for_jira_git_initiatives,
        )

        # Assign Git initiatives to Jira data
        jira_data_df = await calculate_token_count_async(
            jira_data_df, text_columns=["description"], token_column="description_token"
        )
        batches_of_jira_data = get_batches(jira_data_df, tiktoken_column="description_token")
        output_jira_data = await git_topic_assign_to_jira_data(
            batches_of_jira_data,
            git_initiatives,
            task,
            output_path_for_jira_git_initiatives,
            error_log_path_for_jira_git_initiatives,
        )

        end_time_estimates = get_estimated_end_date(output_jira_data, "Categorization_of_initiative_git", jira_only_dir)
        logger.info(f"End time estimates for git initiatives::{end_time_estimates}")

        git_updated_initiatives = add_jira_initiative_completion_percentage(
            git_initiatives,
            output_jira_data,
            end_time_estimates,
            "Categorization_of_initiative_git",
        )

        git_updated_initiatives, jira_df = add_start_date(
            output_jira_data,
            git_updated_initiatives,
            output_path_for_jira_git_initiatives,
            "Categorization_of_initiative_git",
        )

    git_updated_initiatives = normalize_epics_percentage(git_updated_initiatives)

    logger.info("Round percentages")
    round_percentages(
        git_updated_initiatives,
        ("initiative_percentage", "epic_percentage", "percentage_tickets_done"),
    )

    try:
        with open(git_initiatives_path, "w") as file:
            json.dump(git_updated_initiatives, file, indent=4)
        logger.info(f"Successfully saved the updated git initiatives at {git_initiatives_path}")
    except Exception as e:
        logger.exception(f"Pipeline B/C - Error saving git initiatives")

    insights = None
    if jira_data_df is not None and not jira_data_df.empty:  # If Jira data is available
        # Generating the reconciliation insights from the jira and git initiatives
        insights = await reconciliation_insights(git_updated_initiatives, insights_path)

        # Adding the summary for the git initiatives JSON
        git_updated_initiatives = await add_summary(git_updated_initiatives, git_initiatives_path)

        # Adding the expedited delivery date recommendation insights
        git_updated_initiatives = await add_expedited_date_recommendation_insights(
            git_updated_initiatives, git_initiatives_path, today_date
        )

        # Add delivery estimates to Git initiatives
        logger.info("Adding delivery estimates to Git initiatives...")
        git_updated_initiatives = await append_git_delivery_estimates(
            output_data_git,
            jira_df,
            git_updated_initiatives,
            git_initiatives_path,
        )

    initiatives = GitInitiatives.model_validate(git_updated_initiatives)
    acceleration_summary = await generate_acceleration_summary(initiatives)

    return PipelineBCResultItem(
        git_initiatives=initiatives,
        insights=insights,
        acceleration_summary=acceleration_summary,
    )


async def run_pipeline_b_c(
    data_dir: str,
    summary_data_dfs: dict[str, pd.DataFrame],
    repo_group_git_repos: dict[str, list[str]],
    today_date: datetime,
    repo_group_jira_projects: dict[str, list[str]] | None = None,
    confluence_user: str | None = None,
    confluence_token: str | None = None,
    jira_url: str | None = None,
    chat_input: str | None = None,
    jira_access_token: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> PipelineBCResult:
    logger.info(
        f"Running pipeline B/C with params: "
        f"{data_dir=} {confluence_user=} confluence_token~={bool(confluence_token)} "
        f"{jira_url=} {chat_input=} jira_access_token~={bool(jira_access_token)} "
        f"{start_date=} {end_date=}"
    )
    git_folder_path = Path(data_dir)
    output_dir_base = git_folder_path / "git_dataset"
    if not repo_group_jira_projects:
        repo_group_jira_projects = {}

    result_items: dict[str, PipelineBCResultItem] = {}
    for group_name, group_repos in repo_group_git_repos.items():
        output_dir = output_dir_base / str(group_name).replace("/", "___").replace(" ", "_")
        output_dir.mkdir(parents=True, exist_ok=True)
        git_data_path = output_dir / f"{git_folder_path.stem}_git_data_summary.csv"
        if not os.path.exists(git_data_path):
            logger.info("Repo group git data has not been created")
            continue

        git_data_with_summary_df = summary_data_dfs[group_name]
        logger.info(f"Git data loaded. Shape: {git_data_with_summary_df.shape}")
        if not (start_date and end_date):
            start_date = git_data_with_summary_df["date"].min()
            end_date = git_data_with_summary_df["date"].max()

        jira_data_df = None
        with calls_context("pipeline_bc.yaml"):
            jira_project_names = repo_group_jira_projects.get(group_name)
            if ((confluence_user and confluence_token) or jira_access_token) and jira_project_names:
                logger.info(f"Fetching Jira data securely using Confluence token authentication.")
                logger.info(
                    f"Fetching data from date: {start_date} Till date: {end_date} Project names: {jira_project_names}"
                )
                jira_data_df = await process_jira_data(
                    jira_url,
                    jira_project_names,
                    confluence_user,
                    confluence_token,
                    start_date,
                    end_date,
                    jira_access_token,
                )

            if jira_data_df is not None and not jira_data_df.empty:
                logger.info(f"Jira data loaded using Confluence token. Shape: {jira_data_df.shape} ")
            else:
                logger.info(
                    f"Jira data not provided locally, nor fetched via JIRA API. Proceeding with git data.",
                    extra={"jira_project": jira_project_names},
                )

            item = await main(today_date, chat_input, jira_data_df, git_data_with_summary_df, git_data_path)
            result_items[group_name] = item
    return PipelineBCResult(items=result_items)

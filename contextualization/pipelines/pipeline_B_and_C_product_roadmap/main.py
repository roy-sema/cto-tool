import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dateutil import parser as dateutil_parser
from opentelemetry.trace import get_current_span
from otel_extensions import instrumented
from requests.exceptions import HTTPError

from contextualization.conf.config import conf, llm_name
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
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import PipelineBCResult, PipelineBCResultItem
from contextualization.tools.json_tools import round_percentages
from contextualization.tools.llm_tools import (
    calculate_token_count,
    get_batches,
)
from contextualization.utils.csv_loader import load_csv_safely
from contextualization.utils.parse_jira_fields import parse_changelog_data
from contextualization.utils.timezone_independence import (
    adjust_start_and_end_date_for_timezone_independence,
)
from contextualization.utils.vcr_mocks import calls_context

token_limit = conf["llms"][llm_name]["token_limit"]
batch_threshold = conf["llms"][llm_name]["batch_threshold"]


@instrumented
def git_topic_assign_to_git_data(df_lists, topics, task, output_path, error_log_path):
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

    def analyze_change_with_token_callback(batch_content):
        try:
            logging.info("Assigning Git initiatives to the current batch of Git data...")
            outputs = asyncio.run(
                chain_topic_assign_git.abatch(
                    [
                        {
                            "diff_summary": file_content,
                            "topic": result,
                            "task": task,
                        }
                        for file_content in batch_content
                    ]
                )
            )

            logging.info(
                f"Successfully assigned Git initiatives to records of git data.",
                extra={
                    "batches_type": "git_initiatives_git_data",
                },
            )
            return outputs

        except Exception:
            logging.exception("Pipeline B/C - Error processing batch")
            return [None] * len(batch_content)

    batch_number = 0
    try:
        # Process the DataFrame in batches
        for batch in df_lists:
            batch_number += 1
            batch_size = len(batch)
            logging.info(f"Processing Batch {batch_number} with size {batch_size}...")

            # Ensure the 'Summary' column exists
            if "Summary" not in batch.columns:
                raise ValueError("The DataFrame must contain a 'Summary' column.")

            error_records = []

            # Apply the analysis to each entry in the batch
            batch_results = analyze_change_with_token_callback(batch["Summary"].tolist())

            # Convert batch_results to a Series to use .isnan()
            batch_results_series = pd.Series(batch_results)

            # Separate successful and errored results
            success_results = [res for res in batch_results if res is not None]
            error_indices = batch.index[batch_results_series.isna()]
            logging.info(f"Length of successful results obtained for batch {batch_number}: {len(success_results)}")

            # Convert the results to DataFrames with the same index as the batch
            if success_results:
                success_df = pd.DataFrame(success_results, index=batch.index[: len(success_results)])
                updated_batch = batch.merge(success_df, left_index=True, right_index=True)

                # Append the updated batch incrementally to the output CSV
                updated_batch.to_csv(
                    output_path,
                    mode="a",
                    header=not os.path.exists(output_path),  # Only write the header for the first batch
                    index=False,
                )
            if not error_indices.empty:
                # Collect error records for the current batch
                error_records = batch.loc[error_indices]

                # Append to error log CSV file immediately
                error_records.to_csv(
                    error_log_path,
                    mode="a",
                    index=False,
                    header=not os.path.exists(error_log_path),
                )

    except Exception:
        logging.exception("Pipeline B/C - Error occurred while assigning git initiatives to git data batches")

    # Load and return the full, saved DataFrame with original and new columns
    if os.path.exists(output_path):
        return load_csv_safely(output_path)
    else:
        raise FileNotFoundError(f"The file '{output_path}' does not exist.")


def project_exists(
    jira_url: str,
    project_key: str,
    user: str,
    confluence_token: str,
    start_date: str,
    end_date: str,
    jira_access_token: str | None = None,
):
    """
    Check if a project exists in Jira.

    Args:
        jira_url (str): The base URL of Jira.
        project_key (str): The key of the project to check.
        user (str): The username for basic authentication.
        confluence_token (str): The token for basic authentication.
        start_date (str): The start date.
        end_date (str): The end date.
        jira_access_token (str): The access token for Jira API authentication.

    Returns:
        bool: True if the project exists, False otherwise.
    """

    jql_query = f'project="{project_key}" AND created >= "{start_date}" AND created <= "{end_date}"'
    api_url = f"{jira_url}/rest/api/2/search?jql={requests.utils.quote(jql_query)}&maxResults=10&expand=changelog"

    headers = {"Accept": "application/json"}
    if jira_access_token:
        headers["Authorization"] = f"Bearer {jira_access_token}"
        response = requests.get(api_url, headers=headers)
    else:
        response = requests.get(api_url, auth=(user, confluence_token), headers=headers)

    if response.status_code != 200:
        logging.warning(
            f"No project found with key",
            extra={"project_key": project_key, "jira_url": jira_url},
        )
        return False
    else:
        return True


@instrumented
def get_jira_data_contextualization(
    jira_url: str,
    project_names: list,
    user: str,
    confluence_token: str,
    start_date: str,
    end_date: str,
    jira_access_token: str | None = None,
):
    try:
        as_of_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        max_results = 100
        start_at = 0
        total_issues = []

        fields_to_fetch = "key,summary,description,issues,status,issuetype,priority,assignee,created,updated,priority,components,labels,attachment,issuelinks"

        # Project names list - only of projects that exist
        project_names_that_exist = []
        for project in project_names:
            if project_exists(
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
            logging.info("No valid JIRA projects found. Skipping JIRA data fetch.")
            return pd.DataFrame()

        project_list = ",".join([f'"{p}"' for p in project_names_that_exist])

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
                f"jql={requests.utils.quote(jql_query)}"
                f"&fields={fields_to_fetch}"
                f"&maxResults={max_results}&startAt={start_at}&expand=changelog"
            )

            headers = {"Accept": "application/json"}
            if jira_access_token:
                headers["Authorization"] = f"Bearer {jira_access_token}"
                response = requests.get(api_url, headers=headers)
            else:
                response = requests.get(api_url, auth=(user, confluence_token), headers=headers)

            try:
                response.raise_for_status()
            except HTTPError as http_err:
                if response.status_code == 400:
                    logging.exception(
                        "JIRA API returned 400 (Bad Request). Possibly due to malformed JQL or empty project list.",
                        extra={
                            "response_status": response.status_code,
                            "response_text": response.text,
                            "api_url": api_url,
                        },
                    )
                    return pd.DataFrame()
                else:
                    logging.exception(
                        "Error fetching JIRA data",
                        extra={
                            "response_status": response.status_code,
                            "response_text": response.text,
                            "api_url": api_url,
                        },
                    )
                    raise  # re-raise to be caught by outer exception handler

            data = response.json()
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

        logging.info(
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
        logging.exception("Error occurred while fetching JIRA data using JIRA API")
        return pd.DataFrame()


@instrumented
def process_jira_data(
    jira_url: str,
    project_names: list,
    confluence_user: str,
    confluence_token: str,
    start_date: str,
    end_date: str,
    jira_access_token: str | None = None,
):
    """
    Process JIRA data and return a cleaned DataFrame with important columns.
    """
    try:
        original_start_date, original_end_date = start_date, end_date
        """
            Since JQL doesn't allow timezone in the query, we will consider the 
            range [start_date - 48 hours, end_date + 48 hours].
        """
        logging.info(f"Original start_date and end_date: {start_date, end_date}")
        start_date, end_date = adjust_start_and_end_date_for_timezone_independence(start_date, end_date)
        logging.info(f"Adjusted start_date and end_date: {start_date, end_date}")

        df = get_jira_data_contextualization(
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
            logging.warning("No tickets data returned by Jira API")
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
        df["status"] = df["status"].apply(
            lambda x: (x.get("statusCategory", {}).get("name") if isinstance(x, dict) else None)
        )
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
        start_date_filter = pd.to_datetime(original_start_date).date()
        end_date_filter = pd.to_datetime(original_end_date).date()
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
        logging.exception("Pipeline B/C - Error occurred while processing JIRA data")
        return pd.DataFrame()


@instrumented
def git_topic_assign_to_jira_data(df_lists, topics, task, output_path, error_log_path):
    result = ""
    if "initiatives" in topics:
        for index, topic_dict in enumerate(topics["initiatives"], 1):
            # Add numbered topic
            result += f"{index}. Topic: {topic_dict['initiative_name']}\n"

            # Add description with "Description:" prefix
            result += f"   Description: {topic_dict['initiative_description']}\n\n"

    # Check if result is empty after processing
    if not result.strip():  # strip() to remove any extra whitespace
        raise ValueError("No valid initiatives found to process in 'initiatives'. The result is empty.")

    def analyze_change_with_token_callback(batch_content):
        try:
            logging.info("Assigning Git initiatives to the current batch of Jira data...")
            outputs = asyncio.run(
                chain_topic_assign_to_jira_from_git.abatch(
                    [
                        {
                            "jira_description": file_content,
                            "topic": result,
                            "task": task,
                        }
                        for file_content in batch_content
                    ]
                )
            )
            logging.info(
                f"Successfully assigned Git initiatives to records of jira data.",
                extra={
                    "batches_type": "git_initiatives_jira_data",
                },
            )
            return outputs

        except Exception:
            logging.exception("Pipeline B/C - Error processing batch")
            return [None] * len(batch_content)

    batch_number = 0
    try:
        # Process the DataFrame in batches
        for batch in df_lists:
            batch_number += 1
            batch_size = len(batch)
            logging.info(f"Processing Batch {batch_number} with size {batch_size}...")
            # Ensure the 'Summary' column exists
            if "description" not in batch.columns:
                raise ValueError("The DataFrame must contain a 'description' column.")

            error_records = []

            # Apply the analysis to each entry in the batch with
            batch_results = analyze_change_with_token_callback(batch["description"].tolist())

            # Convert batch_results to a Series to use .isna()
            batch_results_series = pd.Series(batch_results)

            # Separate successful and errored results
            success_results = [res for res in batch_results if res is not None]
            logging.info(f"Length of successful results obtained for batch {batch_number}: {len(success_results)}")
            error_indices = batch.index[batch_results_series.isna()]

            # Convert the results to DataFrames with the same index as the batch
            if success_results:
                success_df = pd.DataFrame(success_results, index=batch.index[: len(success_results)])
                updated_batch = batch.merge(success_df, left_index=True, right_index=True)
                # Append the updated batch incrementally to the output CSV
                updated_batch.to_csv(
                    output_path,
                    mode="a",
                    header=not os.path.exists(output_path),  # Only write the header for the first batch
                    index=False,
                )

            if not error_indices.empty:
                # Collect error records for the current batch
                error_records = batch.loc[error_indices]

                # Append to error log CSV file immediately
                error_records.to_csv(
                    error_log_path,
                    mode="a",
                    index=False,
                    header=not os.path.exists(error_log_path),
                )

    except Exception:
        logging.exception("Pipeline B/C - Error occurred while assigning git initiatives to jira data batches")

    # Load and return the full, saved DataFrame with original and new columns
    if os.path.exists(output_path):
        return load_csv_safely(output_path)
    else:
        raise FileNotFoundError(f"The file '{output_path}' does not exist.")


def update_changes_with_percentages(df, data, column_name):
    """
    Updates the 'initiatives' key in the provided JSON-like dictionary `data`
    with the percentages of each category from the DataFrame `df`.

    Parameters:
        df (pd.DataFrame): The DataFrame containing the data.
        data (dict): The JSON-like dictionary containing a 'initiatives' key to update.
        column_name (str): The column in `df` to calculate percentages from.

    Returns:
        dict: The updated `data` dictionary.
    """
    logging.info("Updating the percentage with actual percentages of git initiatives.")
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

    except Exception as e:
        logging.exception(
            f"Pipeline B/C - Error while updating the percentage with actual percentages for git initiatives"
        )
        return data  # Return the original data in case of an error


def add_jira_initiative_completion_percentage(data, jira_data, end_date_dict, initiative_column_label):
    """
    Updates the 'initiatives' key in the provided JSON-like dictionary `data`
    with the percentages of each category from the Jira data.
    """
    logging.info("Updating the completion percentage for each initiative")

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
        logging.info(f"Got percentages of initiatives: {percentage_done_dict}")

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

        logging.info("Updated the completion percentage for each initiative")

        return data

    except Exception as e:
        logging.exception(f"Pipeline B/C - Error while updating the completion percentage of initiatives")
        return data  # Return the original data even in case of an error


@instrumented
def add_summary(input_data: dict[str, Any], file_path: Path):
    """
    Reads a JSON file, processes its data using the summary chain, and updates the file.

    Args:
        input_data: git initiatives data.
        file_path: Path to the JSON file.

    Returns:
        dict: The updated JSON data.
    """
    logging.info("Updating the git initiative json with summary.")
    try:
        # Validate the JSON structure
        if not isinstance(input_data, dict):
            raise TypeError("JSON file content must be a dictionary.")

        # Process the data
        response = summary_chain.invoke({"input_json": input_data})

        # Update the data and write it back to the file
        input_data.update(response)
        with open(file_path, "w") as file:  # Directly open in 'w' mode for overwriting
            json.dump(input_data, file, indent=4)

        logging.info("Updated the git initiative json with summary.")

        return input_data

    except Exception as e:
        logging.exception(f"Pipeline B/C - An error occurred while updating the git initiative json with summary")


def add_start_date(
    data: pd.DataFrame, json_data: dict[str, Any], output_csv: Path, initiative_column_label: str
) -> tuple[dict[str, Any], pd.DataFrame]:
    """
    Adds the earliest 'start_date' for each initiative in the given DataFrame.

    Parameters:
        data (pd.DataFrame): DataFrame containing Jira data labelled with initiatives with 'created' dates.
        json_data (dict): JSON structure containing initiative details.
        output_csv (Path): File path to save the updated CSV.
        initiative_column_label (str): Initiative column name.

    Returns:
        dict: Updated JSON data with 'start_date' added.
        df: DataFrame with Jira data.
    """
    updated_data = None
    try:
        # Ensure 'created' column is in datetime format, dropping invalid values
        data["created"] = pd.to_datetime(data["created"], errors="coerce")
        data = data.dropna(subset=["created"])  # Remove rows where 'created' is NaT

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
        logging.info(f"'start_date' column added to Jira data and saved to {output_csv}")

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
            change["start_date"] = str(start_date_dict.get(initiative_name, None))  # Convert to string for JSON

        logging.info(f"'start_date' added to initiatives successfully")

    except Exception as e:
        logging.exception(f"Pipeline B/C - An error occurred while adding the start_date")

    return json_data, updated_data


def delete_existing_files(*file_paths):
    """Delete specified files if they exist."""
    for file_path in file_paths:
        if file_path.exists():
            os.remove(file_path)
            logging.info(f"Deleted existing file: {file_path}")


@instrumented
def get_estimated_end_date(jira_data, initiative_column_label):
    """takes jira data as input and returns a dictionary with initiatives and
    there end date estimates
    """
    logging.info(f"calculating estimated end date")
    done_status = jira_data[jira_data["status"] == "Done"]
    if done_status.shape[0] == 0:
        return {}

    def parse_jira_datetime(timestamp):
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")

    # Extract the time difference between "In Progress" to "Done"
    def calculate_status_time_difference(changelog):
        """This function calculate the start and end date from jira data
        this function try to fetch start date of a ticket by 2 ways:
            1. if in the jira extracted history we get the date when the task was changed
             to inprogress we take that date
            2. if we do not find the task string in-progress then we make created date as in-progress
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
                            item.get("fromString") == "In Progress"
                            and item.get("toString") == "Done"
                            and done_time is None
                        ):
                            done_time = created_time
                        elif item.get("toString") == "Done" and done_time is None:
                            done_time = created_time
                        elif item.get("toString") == "In Progress":
                            in_progress_time = created_time
            if not in_progress_time:
                in_progress_time = created_time

            if in_progress_time and done_time:
                return (done_time - in_progress_time).total_seconds() / 3600, done_time  # Hours
            return "cannot calculate", "cannot calculate"
        except Exception as e:
            logging.exception(f"Pipeline B/C - An error occurred while adding the start_date")
            return "cannot calculate", "cannot calculate"

    done_status["changelog"] = done_status["changelog"].apply(lambda x: eval(x))
    done_status[["completed_time", "done_date"]] = (
        done_status["changelog"].apply(lambda x: calculate_status_time_difference(x["histories"])).apply(pd.Series)
    )
    logging.info(f"calculating the average time take by task per initiative to complete")
    # Convert 'completed_time' to numeric, setting errors='coerce' to ignore strings
    done_status["completed_time"] = pd.to_numeric(done_status["completed_time"], errors="coerce")
    # Drop rows where 'completed_time' is NaN (caused by conversion errors)
    done_status = done_status.dropna(subset=["completed_time"])
    avg_done_time_for_category = (
        done_status.groupby(initiative_column_label).agg({"completed_time": "mean"}).reset_index()
    )

    logging.info(f"calculating the maximum done date for every initiatve")
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

    def calculate_total_time(row):
        try:
            # Attempt to calculate the total time
            return row["completed_time"] * row["ticket_count"]
        except Exception:
            # Handle any errors and return a fallback value
            return "cannot be calculated"

    # Apply the function row-wise
    count_df["total_time_remaining"] = count_df.apply(calculate_total_time, axis=1)

    def add_hours_to_date(row):
        today = datetime.now()  # Get today's date and time
        updated_date = today + timedelta(hours=row["total_time_remaining"])  # Add hours
        if row["ticket_count"] < 1:
            return row["done_date"].date()
        else:
            return updated_date.date()

    # this will calculate the estimated time if the task is not 100% done and if 100%
    # then return the max date.
    count_df["estimated_end_date"] = count_df.apply(lambda row: add_hours_to_date(row), axis=1).astype(str)
    category_end_date = dict(
        zip(
            count_df[initiative_column_label],
            count_df["estimated_end_date"],
        )
    )

    return category_end_date


async def add_estimated_end_date_insights(input_data):
    logging.info("Adding estimated end date insights to initiatives.")

    initiatives = input_data["initiatives"]
    if not initiatives:
        logging.info("No initiatives to process.")
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
        logging.info(f"Processing {len(batch_inputs)} initiatives with LLM batch processing...")
        try:
            end_date_insights = await end_date_insights_chain.abatch(batch_inputs)

            for insight_result, initiative_idx in zip(end_date_insights, initiative_mappings):
                initiatives[initiative_idx]["estimated_end_date_insights"] = insight_result

        except Exception:
            logging.exception("Error processing end date insights batch")
            for initiative_idx in initiative_mappings:
                initiatives[initiative_idx]["estimated_end_date_insights"] = "Error generating end date insights."

    input_data["initiatives"] = initiatives
    logging.info("Updated the initiatives with estimated end date insights.")

    return input_data


def normalize_epics_percentage(initiatives_json):
    """
    Normalizes epic percentages within each initiative based on its total percentage.
    """

    try:
        for initiative in initiatives_json.get("initiatives", []):
            # Calculate the total epic percentage within an initiative
            total_epic_percentage = sum(epic.get("epic_percentage", 0) for epic in initiative.get("epics", []))

            if total_epic_percentage == 0:
                logging.warning(
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
                logging.info(f"Updated epic percentage for epic {epic['epic_name']}: {normalized_percentage:.2f}")

        return initiatives_json

    except Exception as e:
        logging.exception(f"Pipeline B/C - Error normalizing epic percentages")
        return initiatives_json


@instrumented
def reconciliation_insights(git_initiatives, insights_path):
    insights = []
    try:
        insights = insights_chain.invoke({"git_initiatives": git_initiatives})
        logging.info(f"Extracted the reconciliation insights from the data.")

        # Store the insights into json file
        with open(insights_path, "w") as file:
            json.dump(insights, file, indent=4)
        logging.info(f"Successfully stored the reconciliation insights at {insights_path}")
    except Exception as e:
        logging.exception(f"Pipeline B/C - An error occurred while generating the reconciliation insights")
    return insights


@instrumented
async def add_expedited_date_recommendation_insights(
    initiatives: dict[str, Any], initiative_path: Path
) -> dict[str, Any]:
    """
    Load initiatives from a JSON file, generate recommendation insights, and update the initiatives.
    """
    try:
        current_date = datetime.now()  # Get today's date and time

        # Prepare batch inputs for initiatives that need LLM processing
        batch_inputs = []
        initiative_mappings = []

        logging.info(f"Generating the expedited date recommendation insights..")
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

            except Exception as e:
                logging.exception(f"Pipeline B/C - Error processing batch recommendations")

        # Save the updated initiatives back to the file
        with open(initiative_path, "w") as file:
            json.dump(initiatives, file, indent=4)
        logging.info(f"Updated initiatives with recommendation insights saved to: {initiative_path}")

    except Exception as e:
        logging.exception(f"Pipeline B/C - An error occurred while generating the recommendation insights")

    return initiatives


def main(
    chat_input: str | None = None,
    jira_data_df: pd.DataFrame | None = None,
    git_data_with_summary_df: pd.DataFrame | None = None,
    git_data_summary_csv_path: Path | None = None,
) -> PipelineBCResultItem:
    # Load git data
    logging.info(f"Git data loaded with shape: {git_data_with_summary_df.shape}")

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
    git_data = calculate_token_count(git_data_with_summary_df)

    # Process Git initiatives
    git_initiatives, git_initiatives_path = analyze_git_commits(
        git_data_summary_csv_path, git_data_with_summary_df, chat_input
    )

    # Assign initiatives to Git data
    batches_of_df_git = get_batches(git_data, tiktoken_column="summary_tik_token")

    # Assign Git initiatives to git data
    output_data_git = git_topic_assign_to_git_data(
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
        jira_data_df = calculate_token_count(
            jira_data_df, text_columns=["description"], token_column="description_token"
        )
        batches_of_jira_data = get_batches(jira_data_df, tiktoken_column="description_token")
        output_jira_data = git_topic_assign_to_jira_data(
            batches_of_jira_data,
            git_initiatives,
            task,
            output_path_for_jira_git_initiatives,
            error_log_path_for_jira_git_initiatives,
        )

        end_time_estimates = get_estimated_end_date(output_jira_data, "Categorization_of_initiative_git")
        logging.info(f"End time estimates for git initiatives::{end_time_estimates}")

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

    logging.info("Round percentages")
    round_percentages(
        git_updated_initiatives,
        ["initiative_percentage", "epic_percentage", "percentage_tickets_done"],
    )

    try:
        with open(git_initiatives_path, "w") as file:
            json.dump(git_updated_initiatives, file, indent=4)
        logging.info(f"Successfully saved the updated git initiatives at {git_initiatives_path}")
    except Exception as e:
        logging.exception(f"Pipeline B/C - Error saving git initiatives")

    insights = None
    if jira_data_df is not None and not jira_data_df.empty:  # If Jira data is available
        # Generating the reconciliation insights from the jira and git initiatives
        insights = reconciliation_insights(git_updated_initiatives, insights_path)

        # Adding the summary for the git initiatives JSON
        git_updated_initiatives = add_summary(git_updated_initiatives, git_initiatives_path)

        # Adding the expedited delivery date recommendation insights
        git_updated_initiatives = asyncio.run(
            add_expedited_date_recommendation_insights(git_updated_initiatives, git_initiatives_path)
        )

        # Add delivery estimates to Git initiatives
        logging.info("Adding delivery estimates to Git initiatives...")
        try:
            git_updated_initiatives = asyncio.run(
                append_git_delivery_estimates(
                    output_data_git,
                    jira_df,
                    git_updated_initiatives,
                    git_initiatives_path,
                )
            )
            logging.info(f"Successfully added delivery estimates to Git initiatives at {git_initiatives_path}")
        except Exception as e:
            logging.exception(f"Error adding delivery estimates")

    return PipelineBCResultItem(
        git_initiatives=git_updated_initiatives,
        insights=insights,
    )


def run_pipeline_b_c(
    data_dir: str,
    summary_data_dfs: dict[str, pd.DataFrame],
    repo_group_git_repos: dict[str, list[str]],
    repo_group_jira_projects: dict[str, list[str]] | None = None,
    confluence_user: str | None = None,
    confluence_token: str | None = None,
    jira_url: str | None = None,
    chat_input: str | None = None,
    jira_access_token: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> PipelineBCResult:
    logging.info(
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
            logging.info("Repo group git data has not been created")
            continue

        git_data_with_summary_df = summary_data_dfs[group_name]
        logging.info(f"Git data loaded. Shape: {git_data_with_summary_df.shape}")
        if not (start_date and end_date):
            start_date = git_data_with_summary_df["date"].min()
            end_date = git_data_with_summary_df["date"].max()

        jira_data_df = None
        with calls_context("pipeline_bc.json"):
            jira_project_names = repo_group_jira_projects.get(group_name)
            if ((confluence_user and confluence_token) or jira_access_token) and jira_project_names:
                logging.info(f"Fetching Jira data securely using Confluence token authentication.")
                logging.info(
                    f"Fetching data from date: {start_date} Till date: {end_date} Project names: {jira_project_names}"
                )
                jira_data_df = process_jira_data(
                    jira_url,
                    jira_project_names,
                    confluence_user,
                    confluence_token,
                    start_date,
                    end_date,
                    jira_access_token,
                )

            if jira_data_df is not None and not jira_data_df.empty:
                logging.info(f"Jira data loaded using Confluence token. Shape: {jira_data_df.shape} ")
            else:
                logging.info(
                    f"Jira data not provided locally, nor fetched via JIRA API. Proceeding with git data.",
                    extra={"jira_project": jira_project_names},
                )

            item = main(chat_input, jira_data_df, git_data_with_summary_df, git_data_path)
            result_items[group_name] = item
    return PipelineBCResult(items=result_items)

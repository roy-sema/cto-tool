import asyncio
import json
import logging
import os
import subprocess

import pandas as pd
from otel_extensions import instrumented
from pydantic import ValidationError

from contextualization.conf.config import conf, llm_name
from contextualization.models.anomaly_insights import GitCombinedInsights, GitInsight
from contextualization.pipelines.anomaly_driven_insights.git_diff_anomaly import (
    find_anomalies_in_git_diffs,
)
from contextualization.pipelines.anomaly_driven_insights.prompts.cto_summary import (
    cto_summary_chain_anomaly_insights,
    cto_summary_chain_risk_insights,
)
from contextualization.pipelines.anomaly_driven_insights.prompts.prompt import (
    analyse_chunks_chain,
    analyse_git_tree_chain,
    anomaly_ranking_chain,
    blind_spot_chain,
    skip_a_meeting_chain,
)
from contextualization.tools.llm_tools import (
    calculate_token_count_async,
    get_batches,
    get_batches_to_merge,
)
from contextualization.utils.otel_utils import suppress_prompt_logging
from contextualization.utils.vcr_mocks import calls_context

token_limit = conf["llms"][llm_name]["token_limit"]
batch_threshold = conf["llms"][llm_name]["batch_threshold"]


def generate_git_tree(repo_path, repo_name, start_date, end_date, dir_name) -> tuple[str, int]:
    git_tree_file = os.path.join(dir_name, f"{repo_name}_git_tree_file.txt")
    if os.path.exists(git_tree_file):
        os.remove(git_tree_file)
        logging.info(f"Deleted existing file: {git_tree_file}")
    # git_tree_file = f"{repo_name}_git_tree_file_{timestamp}.txt"
    logging.info(f"Generating git tree for {repo_path}...")

    result = subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "symbolic-ref",
            "--short",
            "refs/remotes/origin/HEAD",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and result.stdout.strip():
        branch_name_acted_on = result.stdout.strip()
    else:
        current_branch_result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        branch_name_acted_on = current_branch_result.stdout.strip()

    # Fetch the git log into memory
    log_result = subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "log",
            f"--since={start_date}",
            f"--until={end_date}",
            "--graph",
            "--oneline",
            branch_name_acted_on,
            "--abbrev=8",
            "--format=%h %s",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    git_tree_content = log_result.stdout

    with open(git_tree_file, "w") as f:
        f.write(git_tree_content)

    commit_count = len(git_tree_content.splitlines())
    logging.info(f"Number of commits (number of lines) in git tree file: {commit_count}")

    return git_tree_content, commit_count


@instrumented
async def find_insights_in_commit_summaries(anamoly_summary_output_df, dir_name, repo_name):
    logging.info("Function to generate summary from anomaly summary")

    required_columns = {"anomaly_summary", "id", "files", "branch_name"}
    if not required_columns.issubset(anamoly_summary_output_df.columns):
        raise ValueError("Missing required columns: 'anomaly_summary' and/or 'id' and/or 'files' and/or branch_name")

    # Create a new column with shortened commit IDs (8 characters)
    anamoly_summary_output_df["short_commit_id"] = anamoly_summary_output_df["id"].astype(str).str[:8]

    # Step 1: Calculate token count for columns
    anamoly_summary_output_df = await calculate_token_count_async(
        anamoly_summary_output_df,
        text_columns=["anomaly_summary", "short_commit_id", "files"],
        token_column="git_anomaly_tik_tokens",
    )

    # Filter and clean up the data
    only_anomaly_summary = anamoly_summary_output_df[
        [
            "anomaly_summary",
            "short_commit_id",
            "files",
            "branch_name",
            "git_anomaly_tik_tokens",
        ]
    ].dropna()

    # Step 2: Create dynamic token-aware batches
    batches = get_batches_to_merge(only_anomaly_summary, tiktoken_column="git_anomaly_tik_tokens")

    # Step 3: Format each batch into a chunk
    chunks = []
    for df in batches:
        row_str = "\n".join(
            (
                df["anomaly_summary"]
                + " | "
                + df["short_commit_id"]
                + " | "
                + str(df["files"])
                + " | "
                + df["branch_name"]
            ).apply(lambda x: x.replace("\n", " "))
        )
        chunks.append(row_str)

    logging.info(f"Total chunks to be processed: {len(chunks)}")

    repo_result_list = await analyse_chunks_chain.abatch([{"chunk": chunk} for chunk in chunks])

    # Step 5: Save the combined output
    path_to_store_json = os.path.join(dir_name, f"{repo_name}_analysis_git_summaries.json")
    with open(path_to_store_json, "w") as json_file:  # noqa: ASYNC230
        json.dump(repo_result_list, json_file, indent=4)

    logging.info(f"Saved analysis file at location: {path_to_store_json}")

    return repo_result_list


@instrumented
async def find_anomaly_insights_in_git_tree_and_commit_summaries(
    repo_name, git_tree_content, dir_name, anamoly_summary_output_df=None
):
    analysis_file = os.path.join(dir_name, f"{repo_name}_analysis_git_tree.txt")
    if os.path.exists(analysis_file):
        os.remove(analysis_file)
        logging.info(f"Deleted existing file analysis git tree file: {analysis_file}")
    logging.info(f"Analyzing git tree for {repo_name}...")

    coroutines = [analyse_git_tree_chain.ainvoke({"git_tree_content": git_tree_content})]
    if anamoly_summary_output_df is not None:
        coroutines.append(find_insights_in_commit_summaries(anamoly_summary_output_df, dir_name, repo_name))

    analysis_result = await asyncio.gather(*coroutines)

    analysis_content = "Analyzing git tree...\n" + analysis_result[0]
    with open(analysis_file, "w") as f:  # noqa: ASYNC230
        f.write(analysis_content)

    git_diff_analysis = None
    if anamoly_summary_output_df is not None:
        git_diff_analysis = analysis_result[1]

    return analysis_content, git_diff_analysis


@instrumented
async def generate_git_diff_summary_for_anomaly_insights(repo_name, analysis_content, git_diff_analysis, dir_name):
    summary_file = os.path.join(dir_name, f"{repo_name}_anomaly_driven_insights.json")
    if os.path.exists(summary_file):
        os.remove(summary_file)
        logging.info(f"Deleted existing cto insights file: {summary_file}")
    # summary_file = f"{repo_name}_summary_{timestamp}.txt"
    logging.info("Synthesizing recommendations...")

    anomaly_insights, risk_insights = await asyncio.gather(
        cto_summary_chain_anomaly_insights.ainvoke(
            {
                "git_tree_analysis_content": analysis_content,
                "git_diff_analysis_content": [item.get("anomaly_insights", "") for item in git_diff_analysis],
            }
        ),
        cto_summary_chain_risk_insights.ainvoke(
            {
                "git_tree_analysis_content": analysis_content,
                "git_diff_analysis_content": [item.get("risk_insights", "") for item in git_diff_analysis],
            }
        ),
    )

    summary_content = {**anomaly_insights, **risk_insights}
    with open(summary_file, "w") as json_file:  # noqa: ASYNC230
        json.dump(summary_content, json_file, indent=4)

    logging.info(f"Saved cto insights file at location: {summary_file}")

    return summary_content


@instrumented
def combine_cto_summary_analysis_and_rank_anomalies(
    repo_list, base_path, summary_contents, max_tokens_per_chunk=50000, model="gpt-4"
):
    anomaly_insights_list = []
    risk_insights_list = []

    # Loop through each repository to collect insights
    for repo in repo_list:
        file_path = os.path.join(base_path, f"{repo}_anomaly_driven_insights.json")
        if not os.path.exists(file_path):
            logging.info(f"Warning: {file_path} not found.")
            raise FileNotFoundError(f"Input file not found: {file_path}")

        data = summary_contents[repo]

        # Extract anomaly insights with evidences
        if "anomaly_insights" in data:
            for insight in data["anomaly_insights"]:
                title = insight.get("title", "")
                category = insight.get("category", "")
                description = insight.get("description", "")
                evidence = insight.get("evidence", "No specific evidence found in commit data")
                significance_score = insight.get("significance_score", "0")
                confidence_level = insight.get("confidence_level", "")
                sources = insight.get("sources", [])
                files = insight.get("files", [])
                # Only use placeholder text if evidence is completely empty
                if not evidence or evidence.strip() == "":
                    evidence = "No specific evidence found in commit data"

                anomaly_insights_list.append(
                    {
                        "repo": repo,
                        "title": title,
                        "category": category,
                        "critical_anomaly": description,  # Use the format expected by anomaly_ranking_chain
                        "insight": description,
                        "evidence": evidence,
                        "significance_score": significance_score,
                        "confidence_level": confidence_level,
                        "sources": sources,
                        "files": files,
                    }
                )

        # Extract risk insights with evidences
        if "risk_insights" in data:
            for insight in data["risk_insights"]:
                category = insight.get("category", "")
                title = insight.get("title", "")
                description = insight.get("description", "")
                evidence = insight.get("evidence", "No specific evidence found in commit data")
                significance_score = insight.get("significance_score", "0")
                confidence_level = insight.get("confidence_level", "")
                sources = insight.get("sources", [])
                files = insight.get("files", [])
                # Only use placeholder text if evidence is completely empty
                if not evidence or evidence.strip() == "":
                    evidence = "No specific evidence found in commit data"

                risk_insights_list.append(
                    {
                        "repo": repo,
                        "title": title,
                        "category": category,
                        "critical_anomaly": description,  # Use the format expected by anomaly_ranking_chain
                        "insight": description,
                        "evidence": evidence,
                        "significance_score": significance_score,
                        "confidence_level": confidence_level,
                        "sources": sources,
                        "files": files,
                    }
                )

    # Rank anomaly insights using anomaly_ranking_chain
    if anomaly_insights_list:
        logging.info(f"Ranking anomaly insights with length::{len(anomaly_insights_list)}")
        max_retries = 3
        attempts = 0

        # Prepare data for ranking
        anomaly_ranking_input = []
        for item in anomaly_insights_list:
            anomaly_ranking_input.append({"repo": item["repo"], "critical_anomaly": item["critical_anomaly"]})

        # Attempt to rank with retries
        while attempts < max_retries:
            try:
                ranked_anomalies = anomaly_ranking_chain.invoke({"analysis_content": anomaly_ranking_input})

                if isinstance(ranked_anomalies, dict) and "critical_anomalies" in ranked_anomalies:
                    logging.info("Successfully ranked anomaly insights")

                    # Create a new ranked list with all original fields
                    ranked_anomaly_list = []
                    for ranked_item in ranked_anomalies["critical_anomalies"]:
                        # Find matching original item to get evidence
                        for orig_item in anomaly_insights_list:
                            if (
                                orig_item["repo"] == ranked_item["repo"]
                                and orig_item["critical_anomaly"] == ranked_item["critical_anomaly"]
                            ):
                                ranked_anomaly_list.append(
                                    {
                                        "repo": orig_item["repo"],
                                        "title": orig_item["title"],
                                        "category": orig_item["category"],
                                        "insight": orig_item["insight"],
                                        "evidence": orig_item["evidence"],
                                        "significance_score": orig_item["significance_score"],
                                        "confidence_level": orig_item["confidence_level"],
                                        "sources": orig_item["sources"],
                                        "files": orig_item["files"],
                                    }
                                )
                                break

                    # Replace the original list with ranked list
                    anomaly_insights_list = ranked_anomaly_list
                    break
            except Exception:
                logging.exception("Pipeline Git anomaly insights - Error ranking anomaly insights")

            attempts += 1
            logging.info(f"Retrying anomaly ranking... ({attempts}/{max_retries})")

    # Rank risk insights using anomaly_ranking_chain
    if risk_insights_list:
        logging.info(f"Ranking risk insights with length::{len(risk_insights_list)}")
        max_retries = 3
        attempts = 0

        # Prepare data for ranking
        risk_ranking_input = []
        for item in risk_insights_list:
            risk_ranking_input.append({"repo": item["repo"], "critical_anomaly": item["critical_anomaly"]})

        # Attempt to rank with retries
        while attempts < max_retries:
            try:
                ranked_risks = anomaly_ranking_chain.invoke({"analysis_content": risk_ranking_input})

                if isinstance(ranked_risks, dict) and "critical_anomalies" in ranked_risks:
                    logging.info("Successfully ranked risk insights")

                    # Create a new ranked list with all original fields
                    ranked_risk_list = []
                    for ranked_item in ranked_risks["critical_anomalies"]:
                        # Find matching original item to get evidence
                        for orig_item in risk_insights_list:
                            if (
                                orig_item["repo"] == ranked_item["repo"]
                                and orig_item["critical_anomaly"] == ranked_item["critical_anomaly"]
                            ):
                                ranked_risk_list.append(
                                    {
                                        "repo": orig_item["repo"],
                                        "title": orig_item["title"],
                                        "category": orig_item["category"],
                                        "insight": orig_item["insight"],
                                        "evidence": orig_item["evidence"],
                                        "significance_score": orig_item["significance_score"],
                                        "confidence_level": orig_item["confidence_level"],
                                        "sources": orig_item["sources"],
                                        "files": orig_item["files"],
                                    }
                                )
                                break

                    # Replace the original list with ranked list
                    risk_insights_list = ranked_risk_list
                    break
            except Exception:
                logging.exception("Pipeline Git anomaly insights - Error ranking risk insights")

            attempts += 1
            logging.info(f"Retrying risk ranking... ({attempts}/{max_retries})")

    # Create the final combined result with ranked insights
    combine_cto_summary_result = {
        "anomaly_insights": anomaly_insights_list,
        "risk_insights": risk_insights_list,
    }

    # Save the combined JSON
    combine_cto_summry_result_file_path = os.path.join(base_path, f"combined_git_anomaly_driven_insights.json")
    with open(combine_cto_summry_result_file_path, "w") as out_file:
        json.dump(combine_cto_summary_result, out_file, indent=4)

    logging.info(f"Saved ranked insights at: {combine_cto_summry_result_file_path}")
    return combine_cto_summary_result, combine_cto_summry_result_file_path


@instrumented
def find_blind_spot_insights(insights, insights_path):
    """
    This function adds blind spot analysis to anomaly insights and risk insights.
    Args:
        insights (dict) insights data.
        insights_path (str): Path to the JSON file containing the insights.
    Returns:
        dict: The updated insights data after adding blind spots.
    """
    # Read the existing insights from the provided JSON file

    # Process 'anomaly_insights' if present
    if "anomaly_insights" in insights:
        logging.info(f"Processing {len(insights['anomaly_insights'])} anomaly insights to add blind spot.")
        results = asyncio.run(blind_spot_chain.abatch(insights["anomaly_insights"]))
        for insight, blind_spot_result in zip(insights["anomaly_insights"], results):
            insight.update(blind_spot_result)

    # Process 'risk_insights' if present
    if "risk_insights" in insights:
        logging.info(f"Processing {len(insights['risk_insights'])} risk insights to add blind spot.")
        results = asyncio.run(blind_spot_chain.abatch(insights["risk_insights"]))
        for insight, blind_spot_result in zip(insights["risk_insights"], results):
            insight.update(blind_spot_result)

    # Save the updated insights back to the file
    with open(insights_path, "w") as file:
        json.dump(insights, file, indent=4)
    logging.info(f"Successfully updated insights with blind spot and saved to {insights_path}")

    return insights


@instrumented
def find_skip_a_meeting_insights(insights, insights_path):
    """
    This function Skip A Meeting insights in anomaly insights and risk insights.

    Args:
        insights (dict): insights data.
        insights_path (str): Path to the JSON file containing the insights.

    Returns:
        dict: The updated insights data after processing.
    """
    # Read the existing insights from the provided JSON file

    # Process 'anomaly_insights' if present
    if "anomaly_insights" in insights:
        logging.info(f"Processing {len(insights['anomaly_insights'])} anomaly insights.")
        results = asyncio.run(
            skip_a_meeting_chain.abatch([{"analysis_content": insight} for insight in insights["anomaly_insights"]])
        )
        for insight, skip_a_meeting_result in zip(insights["anomaly_insights"], results):
            insight.update(skip_a_meeting_result)

    # Process 'risk_insights' if present
    if "risk_insights" in insights:
        logging.info(f"Processing {len(insights['risk_insights'])} risk insights.")
        results = asyncio.run(
            skip_a_meeting_chain.abatch([{"analysis_content": insight} for insight in insights["risk_insights"]])
        )
        for insight, skip_a_meeting_result in zip(insights["risk_insights"], results):
            insight.update(skip_a_meeting_result)

    # Save the updated insights back to the file
    with open(insights_path, "w") as file:
        json.dump(insights, file, indent=4)
    logging.info(f"Successfully updated insights and saved to {insights_path}")

    return insights


@instrumented
async def find_anomaly_insights_for_repo(
    repo_name, repo_path, dir_name, repo_data, start_date, end_date, git_tree_only=False
):
    """
    Generates anomaly insights for a given repository within a specified date range.

    Args:
        repo_name: The name of the repository.
        repo_path: The file system path to the repository.
        dir_name: The directory name where intermediate and output files will be stored.
        repo_data: Git diff summaries for analysis.
        start_date: The start date for the analysis period.
        end_date: The end date for the analysis period.
    """

    logging.info(f"Generating git tree from {start_date} to {end_date}")
    git_tree_content, commit_count = generate_git_tree(repo_path, repo_name, start_date, end_date, dir_name)

    logging.info(f"Analyzing git tree for {repo_name}")
    analysis_content, git_diff_analysis = await find_anomaly_insights_in_git_tree_and_commit_summaries(
        repo_name,
        git_tree_content,
        dir_name,
        repo_data if not git_tree_only else None,
    )

    if git_diff_analysis is None:
        git_diff_analysis = "Git diff analysis not provided."

    return await generate_git_diff_summary_for_anomaly_insights(
        repo_name, analysis_content, git_diff_analysis, dir_name
    )


async def execute_concurrently(coroutines):
    # dirty hack  - asyncio.gather must be called withing async context
    return await asyncio.gather(*coroutines)


def analyse_git_data(
    git_csv_path, main_folder_path, summary_data_df: pd.DataFrame, output_path=None
) -> GitCombinedInsights | None:
    """
    Processes Git repository data within a specified date range, performs analysis,
    and saves outputs dynamically in a folder.
    """
    try:
        if not os.path.exists(git_csv_path):
            logging.info(f"checking if the csv exists for git data")
            raise FileNotFoundError(f"Input file not found: {git_csv_path}")

        if output_path is None:
            dir_name, base_name = os.path.split(git_csv_path)
            name, ext = os.path.splitext(base_name)
            anomaly_summary_output_path = os.path.join(dir_name, f"{name}_anomaly_output{ext}")
            error_log_file = os.path.join(dir_name, f"{name}_error_output{ext}")
        else:
            logging.info("Creating path for error output folders")
            # Just reuse the original file name structure
            base_name = os.path.basename(git_csv_path)
            name, ext = os.path.splitext(base_name)
            anomaly_summary_output_path = os.path.join(output_path, f"{name}_anomaly_output{ext}")
            error_log_file = os.path.join(output_path, f"{name}_error_output{ext}")

        # Gather and process repository data
        logging.info(f"Gathering data from git repositories")
        data = summary_data_df
        logging.info(f"shape of data from git loaded: {data.shape}")

        dataframes = get_batches(data, tiktoken_column="tik_tokens")

        # Analyze code changes and save results
        with suppress_prompt_logging():
            summary_data = find_anomalies_in_git_diffs(dataframes, anomaly_summary_output_path, error_log_file)
        logging.info("extracted anomaly summary data")

        # Convert to datetime (ensure it includes time)
        summary_data["date"] = pd.to_datetime(summary_data["date"])

        # Get min and max dates
        start_date = summary_data["date"].min().normalize()  # Set to 00:00:00
        end_date = summary_data["date"].max().normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)

        # raise Exception(anomaly_summary_output_path)

        repo_list = []
        summary_contents = {}
        coroutines = []
        repo_names = []
        for repo_name in os.listdir(main_folder_path):
            repo_path = os.path.join(main_folder_path, repo_name)
            # Check if the path is a directory and contains a .git folder
            if os.path.isdir(repo_path) and ".git" in os.listdir(repo_path):
                logging.info(f"Processing repository: {repo_name}")
                repo_data = summary_data[summary_data["repository"] == repo_name]
                if repo_data.shape[0] > 0:
                    logging.info(f"Found data for anomaly summary: {repo_data.shape[0]}")
                    repo_list.append(repo_name)
                    coroutines.append(
                        find_anomaly_insights_for_repo(repo_name, repo_path, dir_name, repo_data, start_date, end_date)
                    )
                    repo_names.append(repo_name)
                else:
                    logging.info(f"Data not found for anomaly summary skipping this repo")
            else:
                logging.info(f"skipping directory repository: {repo_name}")
        if len(repo_list) > 0:
            results = asyncio.run(execute_concurrently(coroutines))
            summary_contents = {repo_name: result for repo_name, result in zip(repo_names, results)}
            logging.info(f"combining cto based anomaly insights summary")
            combined_anomaly_insights, combined_anomaly_insights_path = combine_cto_summary_analysis_and_rank_anomalies(
                repo_list, dir_name, summary_contents
            )
            find_blind_spot_insights(combined_anomaly_insights, combined_anomaly_insights_path)
            find_skip_a_meeting_insights(combined_anomaly_insights, combined_anomaly_insights_path)
            try:
                anomaly_insights = [GitInsight(**anomaly) for anomaly in combined_anomaly_insights["anomaly_insights"]]
                risk_insights = [GitInsight(**risk) for risk in combined_anomaly_insights["risk_insights"]]
                combined_insights = GitCombinedInsights(anomaly_insights=anomaly_insights, risk_insights=risk_insights)
            except ValidationError:
                logging.exception("Pipeline Git anomaly insights - Error creating pipeline result")
                return None

            return combined_insights
        else:
            logging.info(f"No repositories found to combining git tree based anomaly insights summary")

    except Exception:
        logging.exception("Pipeline Git anomaly insights - An error occurred")


def run_anomaly_driven_insights(
    git_data_path: str,
    git_repo_path: str,
    summary_data_df: pd.DataFrame,
    output_path: str | None = None,
) -> GitCombinedInsights | None:
    logging.info(f"Running anomaly insights pipeline with params: {git_data_path=} {git_repo_path=} {output_path=}")
    with calls_context("anomaly_driven_insights.json"):
        return analyse_git_data(git_data_path, git_repo_path, summary_data_df, output_path)

import logging
import os
from pathlib import Path

import pandas as pd
from asgiref.sync import sync_to_async
from opentelemetry.trace import get_current_span
from pydantic import BaseModel, ConfigDict, Field

from compass.dashboard.models import GitDiffContext
from contextualization.pipelines.pipeline_A_automated_process.git_data_extraction import (
    gather_process_all_repos_data,
    save_collection_to_csv,
)
from contextualization.pipelines.pipeline_A_automated_process.git_diff_summary import (
    analyze_code_changes_collection,
)
from contextualization.pipelines.pipeline_A_automated_process.main_insights import (
    get_git_work_categorization_and_quantification,
)
from contextualization.pipelines.pipeline_A_automated_process.models import CommitCollection
from contextualization.utils.custom_exceptions import NoCommitsFoundError
from contextualization.utils.otel_utils import suppress_prompt_logging
from contextualization.utils.vcr_mocks import calls_context


class GitAnalysisResults(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_code_commit_count: int
    summary_data_dfs: dict[str, pd.DataFrame] = Field(default_factory=dict)
    summary_data_all_repos: CommitCollection = Field(default_factory=CommitCollection)


async def analyse_git_data(
    git_folder_path: Path,
    start_date: str,
    end_date: str,
    output_path: str | None = None,
    repo_group_git_repos: dict[str, list[str]] = None,
    force: bool = False,
) -> GitAnalysisResults:
    if output_path:
        output_dir_base = Path(output_path)
    else:
        output_dir_base = git_folder_path / "git_dataset"

    all_repos_with_summaries = CommitCollection()
    repo_group_summary_data_dfs: dict[str, pd.DataFrame] = {}
    for repo_name in os.listdir(git_folder_path):
        git_diffs = await gather_process_all_repos_data(
            git_folder_path,
            start_date=start_date,
            end_date=end_date,
            repos=[repo_name],
        )
        if git_diffs.is_empty():
            continue

        if not force:  # Fill with saved results in db
            git_diffs = await sync_to_async(fill_already_analysed_diffs_collection)(git_diffs)

        with suppress_prompt_logging():
            diffs_with_summaries = await analyze_code_changes_collection(git_diffs)

        if not diffs_with_summaries.is_empty():
            all_repos_with_summaries.commits.extend(diffs_with_summaries.commits)

            output_dir = output_dir_base / "all_repos"
            output_dir.mkdir(parents=True, exist_ok=True)
            summaries_output_file = output_dir / "__contextualization_git_data_summary.csv"
            all_repos_df_with_summaries = save_collection_to_csv(diffs_with_summaries, summaries_output_file)
            if not repo_group_git_repos:
                repo_group_summary_data_dfs["all_repos"] = all_repos_df_with_summaries

            categorization_output_file = output_dir / "__contextualization_git_data_overall_summary_final.json"
            await get_git_work_categorization_and_quantification(diffs_with_summaries, categorization_output_file)

    if not repo_group_git_repos:  # Is None or empty
        return GitAnalysisResults(
            total_code_commit_count=len(all_repos_with_summaries.commits),
            summary_data_all_repos=all_repos_with_summaries,
            summary_data_dfs=repo_group_summary_data_dfs,
        )

    for group_name, group_repos in repo_group_git_repos.items():
        logging.info("Processing repo group", extra={"repo_group_name": group_name, "repo_names": group_repos})
        diffs_with_summaries = all_repos_with_summaries.filter_by_repos(group_repos)
        if diffs_with_summaries.is_empty():
            logging.info("No commits for repo group", extra={"repo_group_name": group_name})
            continue

        output_dir = output_dir_base / str(group_name).replace("/", "___").replace(" ", "_")
        output_dir.mkdir(parents=True, exist_ok=True)

        summaries_output_file = output_dir / "__contextualization_git_data_summary.csv"
        repo_group_summary_data_dfs[group_name] = save_collection_to_csv(diffs_with_summaries, summaries_output_file)

        categorization_output_file = output_dir / "__contextualization_git_data_overall_summary_final.json"
        await get_git_work_categorization_and_quantification(diffs_with_summaries, categorization_output_file)

    return GitAnalysisResults(
        total_code_commit_count=len(all_repos_with_summaries.commits),
        summary_data_all_repos=all_repos_with_summaries,
        summary_data_dfs=repo_group_summary_data_dfs,
    )


def fill_already_analysed_diffs_collection(git_diffs: CommitCollection) -> CommitCollection:
    if git_diffs.is_empty():
        return git_diffs

    # Get all commit SHAs from the input data
    commit_shas = [commit.id for commit in git_diffs.commits]

    # Query GitDiffContext to get existing analysis data
    existing_records = GitDiffContext.objects.filter(
        sha__in=commit_shas,
        summary__isnull=False,
        summary__gt="",
    ).values(
        "sha",
        "summary",
        "category",
        "maintenance_relevance",
        "description_of_maintenance_relevance",
        "purpose_of_change",
        "impact_on_product",
    )

    # Convert to dictionary for faster lookup
    analysis_data = {
        record["sha"]: {
            "Summary": record["summary"],
            "Categorization_of_Changes": record["category"],
            "Maintenance_Relevance": record["maintenance_relevance"],
            "Description_of_Maintenance_Relevance": record["description_of_maintenance_relevance"],
            "Purpose_of_change": record["purpose_of_change"],
            "Impact_on_product": record["impact_on_product"],
        }
        for record in existing_records
    }

    # Fill the analysis fields for commits that have existing data
    for commit in git_diffs.commits:
        if commit.id not in analysis_data:
            continue
        data = analysis_data[commit.id]
        commit.Summary = data["Summary"]
        commit.Categorization_of_Changes = data["Categorization_of_Changes"]
        commit.Maintenance_Relevance = data["Maintenance_Relevance"]
        commit.Description_of_Maintenance_Relevance = data["Description_of_Maintenance_Relevance"]
        commit.Purpose_of_change = data["Purpose_of_change"]
        commit.Impact_on_product = data["Impact_on_product"]

    return git_diffs


async def run_pipeline_a(
    git_folder_path: str,
    start_date: str,
    end_date: str,
    output_path: str | None = None,
    repo_group_git_repos: dict[str, list[str]] | None = None,
    run_for_commit_count: bool = False,
    force: bool = False,
) -> GitAnalysisResults:
    logging.info(
        f"Executing pipeline A with params: "
        f"{git_folder_path=} {start_date=} {end_date=} {output_path=} {repo_group_git_repos=} "
        f"{run_for_commit_count=}"
    )

    with calls_context("pipeline_a.yaml"):
        if run_for_commit_count:
            total_code_commit_count = 0
            for repo_name in os.listdir(git_folder_path):
                all_repos_collection = await gather_process_all_repos_data(
                    git_folder_path,
                    start_date=start_date,
                    end_date=end_date,
                    repos=[repo_name],
                )
                commit_count = len(all_repos_collection)
                get_current_span().set_attribute("commit_count", commit_count)
                total_code_commit_count += commit_count

            if total_code_commit_count > 0:
                logging.info("Non-zero code commits found.", extra={"commit_count": commit_count})
            else:
                raise NoCommitsFoundError("No commits with code found for any repository")

            return GitAnalysisResults(total_code_commit_count=total_code_commit_count)
        else:
            return await analyse_git_data(
                Path(git_folder_path), start_date, end_date, output_path, repo_group_git_repos, force=force
            )

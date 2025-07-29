import logging
import os
from pathlib import Path

import pandas as pd
from opentelemetry.trace import get_current_span
from pydantic import BaseModel, ConfigDict

from contextualization.pipelines.pipeline_A_automated_process.git_data_extraction import (
    gather_process_all_repos_data,
)
from contextualization.pipelines.pipeline_A_automated_process.git_diff_summary import (
    analyze_code_changes,
)
from contextualization.pipelines.pipeline_A_automated_process.main_insights import (
    get_git_work_categorization_and_quantification,
)
from contextualization.pipelines.pipeline_A_automated_process.prompts.prompt import (
    get_dev_activity_categories_from_json,
)
from contextualization.pipelines.pipeline_A_automated_process.task1 import (
    count_changes_per_repository,
)
from contextualization.tools.llm_tools import get_batches
from contextualization.utils.custom_exceptions import NoCommitsFoundError
from contextualization.utils.otel_utils import suppress_prompt_logging
from contextualization.utils.vcr_mocks import calls_context


class GitAnalysisResults(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_code_commit_count: int
    summary_data_dfs: dict[str, pd.DataFrame]


def analyse_git_data(
    git_folder_path: Path,
    start_date: str,
    end_date: str,
    output_path: str | None = None,
    repo_group_git_repos: dict[str, list[str]] | None = None,
    run_for_commit_count: bool = False,
) -> GitAnalysisResults:
    if output_path:
        output_dir_base = Path(output_path)
    else:
        output_dir_base = git_folder_path / "git_dataset"

    summary_data_dfs: dict[str, pd.DataFrame] = {}
    total_code_commit_count = 0  # We only consider commits with code.

    if repo_group_git_repos is None:
        all_repos = [repo_name for repo_name in os.listdir(git_folder_path)]
        repo_group_git_repos = {"all_repos": all_repos}

    for group_name, group_repos in repo_group_git_repos.items():
        logging.info("Processing repo group", extra={"repo_group_name": group_name, "repo_names": group_repos})

        output_dir = output_dir_base / str(group_name).replace("/", "___").replace(" ", "_")
        output_dir.mkdir(parents=True, exist_ok=True)

        git_data_output_path = output_dir / f"{git_folder_path.stem}_git_data.csv"
        output_file = output_dir / f"{git_data_output_path.stem}_summary.csv"
        error_log_file = output_dir / f"{git_data_output_path.stem}_error_log.csv"
        count_output_json = output_dir / f"{git_data_output_path.stem}_count.json"

        data = gather_process_all_repos_data(
            git_folder_path,
            start_date,
            end_date,
            git_data_output_path,
            group_repos,
        )

        commit_count = len(data)
        get_current_span().set_attribute("commit_count", commit_count)
        logging.info(
            f"Commit count: {commit_count} for group_repos: {group_repos}",
            extra={
                "commit_count": commit_count,
                "group_repos": group_repos,
            },
        )
        if commit_count == 0:
            logging.info(
                f"No commits with code found for the given date range for group_repos: {group_repos}",
                extra={"group_repos": group_repos},
            )
            continue
        else:
            total_code_commit_count += commit_count
            if run_for_commit_count:
                continue

        if not run_for_commit_count:
            dataframes = get_batches(data, tiktoken_column="tik_tokens")
            logging.info(
                f"Collected git data batches count: {len(dataframes)}",
                extra={
                    "batches_count": len(dataframes),
                    "batches_type": "git_data",
                },
            )

            with suppress_prompt_logging():
                summary_data = analyze_code_changes(dataframes, output_file, error_log_file)
            logging.info("Extracted code changes summary data")

            if summary_data is None:
                logging.error("Pipeline A - No summaries for git diff were created")
                continue

            summary_data["Categorization_of_Changes"] = summary_data["Categorization_of_Changes"].apply(
                lambda json_cat: get_dev_activity_categories_from_json(json_cat)
            )
            summary_data_dfs[group_name] = summary_data
            summary_data.to_csv(output_file, index=False)
            changes_per_repository = count_changes_per_repository(summary_data, count_output_json)
            git_summary = get_git_work_categorization_and_quantification(summary_data, output_dir, git_data_output_path)

    logging.info(f"Total code commit count: {total_code_commit_count}")

    return GitAnalysisResults(
        total_code_commit_count=total_code_commit_count,
        summary_data_dfs=summary_data_dfs,
    )


def run_pipeline_a(
    git_folder_path: str,
    start_date: str,
    end_date: str,
    output_path: str | None = None,
    repo_group_git_repos: dict[str, list[str]] | None = None,
    run_for_commit_count: bool = False,
) -> GitAnalysisResults:
    logging.info(
        f"Executing pipeline A with params: "
        f"{git_folder_path=} {start_date=} {end_date=} {output_path=} {repo_group_git_repos=} "
        f"{run_for_commit_count=}"
    )

    with calls_context("pipeline_a.json"):
        if run_for_commit_count:
            git_analysis_results = analyse_git_data(
                Path(git_folder_path),
                start_date,
                end_date,
                output_path,
                repo_group_git_repos,
                run_for_commit_count=True,
            )
            commit_count = git_analysis_results.total_code_commit_count
            get_current_span().set_attribute("commit_count", commit_count)

            if commit_count > 0:
                logging.info("Non-zero code commits found.", extra={"commit_count": commit_count})
            else:
                raise NoCommitsFoundError("No commits with code found for any repository")

            return git_analysis_results
        else:
            return analyse_git_data(
                Path(git_folder_path),
                start_date,
                end_date,
                output_path,
                repo_group_git_repos,
            )

import argparse
import os
import warnings
from pathlib import Path

from pipelines.anomaly_driven_insights.main import (
    find_anomaly_insights_for_repo,
    generate_git_tree,
)

# from logging_config import setup_logging
warnings.filterwarnings("ignore")

configure_sentry_for_contextualization()


def fast_analyze_git_data(
    main_folder_path: str, start_date: str, end_date: str, output_path: str | None = None
) -> None:
    main_folder_path = Path(main_folder_path)
    if output_path:
        output_dir = Path(output_path)
    else:
        output_dir = main_folder_path / "git_dataset"
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_name_with_max_commits = None
    max_commits = 0
    for repo_name in os.listdir(main_folder_path):
        repo_path = os.path.join(main_folder_path, repo_name)
        # Check if the path is a directory and contains a .git folder
        if os.path.isdir(repo_path) and ".git" in os.listdir(repo_path):
            logger.info(f"Generating git tree for {repo_name} from {start_date} to {end_date}")
            git_tree_content, commit_count = generate_git_tree(repo_path, repo_name, start_date, end_date, output_dir)
            logger.info(f"Git tree for {repo_name} has {commit_count} commits")

            if commit_count > max_commits:
                max_commits = commit_count
                repo_name_with_max_commits = repo_name
        else:
            logger.info(f"skipping directory repository: {repo_name}")

    if repo_name_with_max_commits is None:
        logger.error(
            f"No commits in repositories",
            extra={
                "main_folder_path": main_folder_path,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return

    repo_path = os.path.join(main_folder_path, repo_name_with_max_commits)
    logger.info(f"Processing repository: {repo_name_with_max_commits}")
    logger.info(f"Use only Git tree to find anomalies.")
    summary_content = find_anomaly_insights_for_repo(
        repo_name_with_max_commits,
        repo_path,
        output_dir,
        None,
        start_date,
        end_date,
        git_tree_only=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fast anomaly insights generator to show at onboarding")
    parser.add_argument(
        "--git_repo_path",
        type=str,
        required=True,
        help="Path to the repository folder that contains all Git repositories",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        required=False,
        default=None,
        help="Optional path to save the output files. If not provided, defaults to 'git_dataset' within the git folder path.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Analysis start date in ISO format (e.g., 2024-05-01T00:00:00)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="Analysis end date in ISO format (e.g., 2024-05-30T23:59:59)",
    )

    # Parse the arguments
    args = parser.parse_args()
    # Assign arguments to variables
    output_path = args.output_path
    git_repo_path = args.git_repo_path
    main_folder_path = git_repo_path
    start_date = args.start_date
    end_date = args.end_date

    fast_analyze_git_data(main_folder_path, start_date, end_date, output_path)

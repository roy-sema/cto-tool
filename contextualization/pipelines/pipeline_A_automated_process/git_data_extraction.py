import logging
import os
import subprocess
from datetime import datetime, timedelta

import pandas as pd
import tiktoken
from otel_extensions import instrumented

from contextualization.conf.config import conf, llm_name
from contextualization.utils.file_filters import filter_irrelevant_files

token_limit = conf["llms"][llm_name]["token_limit"]


def is_commit_start_line(line):
    if line and "|" in line and "---COMMIT_STARTS_HERE---" in line:
        return True
    return False


def parse_commit_start_line(line, all_data, repo_name):
    # Split by '|' to handle whitespaces in the name and filenames
    commit_info = line.split("|")
    current_commit_id = commit_info[0].replace("---COMMIT_STARTS_HERE---", "")
    current_commit_name = commit_info[1]
    current_commit_timestamp = commit_info[2]
    current_commit_title = commit_info[3]

    all_data[current_commit_id] = {
        "repository": repo_name,
        "id": current_commit_id,
        "name": current_commit_name,
        "timestamp": current_commit_timestamp,
        "commit_title": current_commit_title,
        "commit_description": "",
        "files": [],
    }

    return current_commit_id, all_data


def get_commit_data_as_dataframe(repo_path, repo_name, start_date, end_date):
    """
    Context - CON-264
    We will run git log on [start_date - 24 hours, end_date + 24 hours], and then
        fiter out commits based on start_date <= commit_date.date() <= end_date
    """

    one_day_before_start_date = (datetime.fromisoformat(start_date) - timedelta(days=1)).isoformat()
    one_day_after_end_date = (datetime.fromisoformat(end_date) + timedelta(days=1)).isoformat()

    # Run the git command to get commit logs with file names
    git_log_command = [
        "git",
        "-C",
        repo_path,
        "log",
        f"--since={one_day_before_start_date}",
        f"--until={one_day_after_end_date}",
        "--pretty=format:---COMMIT_STARTS_HERE---%H|%an|%ad|%B%n---COMMIT_MESSAGE_END---",
        "--date=iso-strict",  # Changed to iso-strict to preserve timezone info
        "--name-only",
        "--diff-filter=AM",
    ]

    # Try to get the default remote branch
    result = subprocess.run(
        ["git", "-C", repo_path, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )

    # Use the default branch if found
    if result.returncode == 0 and result.stdout.strip():
        default_branch = result.stdout.strip()  # e.g., 'origin/main'
        git_log_command.append(default_branch)
        branch_name_acted_on = default_branch
        logging.info(
            f"[Git Log] Using remote default branch '{default_branch}' with {result=}",
            extra={"repo_name": repo_name},
        )
    else:
        # fallback: use the current checked-out branch
        current_branch_result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        current_branch = current_branch_result.stdout.strip()
        git_log_command.append(current_branch)
        branch_name_acted_on = current_branch
        logging.warning(
            f"[Git Log] Remote HEAD not found with {result=}: '{current_branch=}'",
            extra={"repo_name": repo_name},
        )

    logging.info(
        f"[Git Log] Command: {' '.join(git_log_command)}",
        extra={"repo_name": repo_name},
    )

    result = subprocess.run(git_log_command, capture_output=True, text=True)
    # Parse the output
    lines = result.stdout.splitlines()

    all_data = {}
    current_commit_id = None
    is_current_commit_description_parsed = False
    is_current_commit_id_parsed = False

    for line in lines:
        if (
            is_commit_start_line(line) and not is_current_commit_id_parsed
        ):  # Detect commit hash, author name, and date lines
            current_commit_id, all_data = parse_commit_start_line(line, all_data, repo_name)
            is_current_commit_id_parsed = True
            is_current_commit_description_parsed = False
        elif is_current_commit_id_parsed and not is_current_commit_description_parsed:
            if "---COMMIT_MESSAGE_END---" not in line:
                all_data[current_commit_id]["commit_description"] += line + "\n"
            else:
                is_current_commit_description_parsed = True
        else:
            if not is_commit_start_line(line):
                if line:  # Collect file names for the current commit
                    all_data[current_commit_id]["files"].append(line)
                is_current_commit_id_parsed = False
                is_current_commit_description_parsed = False
            elif is_commit_start_line(line):
                current_commit_id, all_data = parse_commit_start_line(line, all_data, repo_name)
                is_current_commit_id_parsed = True
                is_current_commit_description_parsed = False

    # Convert the dictionary to a list of dictionaries for DataFrame creation
    all_list = [all_data[k] for k in all_data.keys()]

    # Create DataFrame
    df = pd.DataFrame(all_list)

    branch_name_acted_on = branch_name_acted_on.strip()
    if branch_name_acted_on:
        parts = branch_name_acted_on.split("/")
        if len(parts) > 2:
            branch_name_acted_on = "/".join(parts[2:])
        else:
            branch_name_acted_on = parts[-1] if parts else None
    else:
        branch_name_acted_on = None

    df["branch_name"] = branch_name_acted_on
    logging.info(
        f"[Git Log] Final branch used: {branch_name_acted_on=}, df.shape={df.shape}",
        extra={"repo_name": repo_name},
    )

    return df


def get_code_changes_for_dataframe(df, repo_path, repo_name):
    # Define a helper function to get the full code changes for each commit
    def get_code_changes(commit_id):
        # Define the command to get the full changes for the specific commit
        commit_sha = str(commit_id) + "^!"
        command = ["git", "diff", commit_sha]

        try:
            result = subprocess.run(
                command, cwd=repo_path, capture_output=True, text=True, errors="ignore"
            )  # Ignore decoding errors

            if result.returncode == 0:
                # If the command is successful, return the changes
                logging.info(f"Git diff commit {commit_id} with returncode=0", extra={"repo_name": repo_name})
                return result.stdout
            else:
                logging.error(
                    f"Pipeline A - Error in a commit",
                    extra={
                        "commit_sha": commit_sha,
                        "sterr": result.stderr,
                    },
                )
                return None  # Returning None for error cases

        except Exception:
            logging.exception(
                "Pipeline A - Error in commit",
                extra={
                    "commit_sha": commit_sha,
                },
            )
            return None

    if not df.empty:
        # Apply the helper function to each row of the DataFrame
        df["code"] = df.apply(lambda row: get_code_changes(row["id"]), axis=1)

    return df


def postprocess_dataframe(df, start_date, end_date):
    """
    Postprocesses a DataFrame by filtering rows based on a date range and removing rows with null values.

    Parameters:
    - df (pd.DataFrame): The input DataFrame.
    - date_column (str): The name of the date column to filter on.
    - start_date (str): The start date for filtering in 'YYYY-MM-DD' format.
    - end_date (str): The end date for filtering in 'YYYY-MM-DD' format.

    Returns:
    - pd.DataFrame: The postprocessed DataFrame.
    """
    if df.empty:
        return df

    # Convert the date column to datetime if not already
    logging.info("converting date column to date time type")

    # convert timestamp to date using string logic rather than any kind of conversion logic
    df["date"] = df["timestamp"].apply(lambda timestamp: timestamp.split("T")[0])
    df["date"] = pd.to_datetime(df["timestamp"], errors="coerce").apply(lambda x: x.date() if pd.notnull(x) else None)

    start_date_filter = pd.to_datetime(start_date.split("T")[0]).date()
    end_date_filter = pd.to_datetime(end_date.split("T")[0]).date()

    df = df[(df["date"] >= start_date_filter) & (df["date"] <= end_date_filter)]

    # drop the timestamp colum
    df = df.drop(columns=["timestamp"])

    logging.info("filtering of dataframe for given start and end time done")
    # Drop rows with null values in any column
    cleaned_df = df.dropna()

    return cleaned_df


def count_tokens(df, column="code", model="gpt-3.5-turbo"):
    if df.empty:
        return df

    # Load the encoding for the specified model
    encoding = tiktoken.encoding_for_model(model)

    # Define a function to trim text for each record and calculate token count
    def trim_text_and_count(text):
        return len(encoding.encode(text)) + 1500

    # Apply the trimming and token counting function to the DataFrame
    df["tik_tokens"] = df[column].apply(trim_text_and_count)

    return df


@instrumented
def gather_process_all_repos_data(
    main_folder_path,
    start_date,
    end_date,
    git_data_output_path,
    repos,
):
    main_df = pd.DataFrame()  # Initialize an empty DataFrame to store data from all repositories

    # Iterate over each folder in the main folder path
    for repo_name in os.listdir(main_folder_path):
        # Check if the repository is in the list of repositories to process
        if repo_name not in repos:
            continue

        repo_path = os.path.join(main_folder_path, repo_name)

        # Check if the path is a directory and contains a .git folder
        if os.path.isdir(repo_path) and ".git" in os.listdir(repo_path):
            logging.info(f"Processing repository: {repo_name}")
            repo_df = get_commit_data_as_dataframe(repo_path, repo_name, start_date, end_date)
            logging.info(f"getting code changes for: {repo_name}: with shape {repo_df.shape}")
            repo_df = get_code_changes_for_dataframe(repo_df, repo_path, repo_name)
            logging.info(f"got code changes for: {repo_name}: with shape {repo_df.shape}")

            repo_df = filter_irrelevant_files(repo_df)
            repo_df = postprocess_dataframe(repo_df, start_date, end_date)
            logging.info(
                f"shape for repo: {repo_name}: after removing null rows and filtering by date: {repo_df.shape}"
            )
            repo_df = count_tokens(repo_df)
            logging.info(f"shape for repo: {repo_name}: after trimming records: {repo_df.shape}")

            # Append the repository data to the main DataFrame, excluding empty dataframes
            if not repo_df.empty:
                main_df = pd.concat([main_df, repo_df], ignore_index=True)
        else:
            logging.info(f"Skipping {repo_name}: {repo_path} is not a git repository")

    logging.info(f"Saving Dataframe with shape: {main_df.shape}")
    main_df.to_csv(git_data_output_path, index=False)
    logging.info(f"Saved Dataframe")
    return main_df

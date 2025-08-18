import asyncio
import logging
import os
from datetime import datetime

import pandas as pd
import tiktoken
from otel_extensions import instrumented

from contextualization.conf.config import conf, llm_name
from contextualization.pipelines.pipeline_A_automated_process.models import CommitCollection, CommitData
from contextualization.utils.file_filters import filter_irrelevant_files_records


class Result:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


token_limit = conf["llms"][llm_name]["token_limit"]


def is_commit_start_line(line: str) -> bool:
    if line and "|" in line and "---COMMIT_STARTS_HERE---" in line:
        return True
    return False


def parse_commit_start_line(line: str, all_data: dict, repo_name: str) -> tuple[str, dict]:
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


async def get_commit_data_as_collection(
    repo_path: str, repo_name: str, start_date: str, end_date: str
) -> CommitCollection:
    env = os.environ.copy()
    # simple way to set consistency between prod and e2e, CI and local
    env["TZ"] = "UTC"
    # Run the git command to get commit logs with file names
    git_log_command = [
        "git",
        "-C",
        repo_path,
        "log",
        f"--since={start_date}",
        f"--until={end_date}",
        "--pretty=format:---COMMIT_STARTS_HERE---%H|%an|%ad|%B%n---COMMIT_MESSAGE_END---",
        "--date=iso-strict",  # Changed to iso-strict to preserve timezone info
        "--name-only",
        "--diff-filter=AM",
    ]

    # Try to get the default remote branch
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        repo_path,
        "symbolic-ref",
        "--short",
        "refs/remotes/origin/HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await process.communicate()
    result = Result(process.returncode, stdout.decode(), stderr.decode())

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
        process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            repo_path,
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()
        current_branch_result = Result(process.returncode, stdout.decode(), stderr.decode())
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

    process = await asyncio.create_subprocess_exec(
        *git_log_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await process.communicate()
    result = Result(process.returncode, stdout.decode(), stderr.decode())
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

    branch_name_acted_on = branch_name_acted_on.strip()
    if branch_name_acted_on:
        parts = branch_name_acted_on.split("/")
        if len(parts) > 2:
            branch_name_acted_on = "/".join(parts[2:])
        else:
            branch_name_acted_on = parts[-1] if parts else None
    else:
        branch_name_acted_on = None

    # Create CommitCollection from parsed data
    commits = []
    for commit_data in all_data.values():
        # Add branch name and create temporary date from timestamp
        commit_data["branch_name"] = branch_name_acted_on
        commit_data["date"] = datetime.fromisoformat(commit_data["timestamp"]).date()
        # Remove timestamp as it's now converted to date
        del commit_data["timestamp"]
        commits.append(CommitData(**commit_data))

    collection = CommitCollection(commits=commits)
    logging.info(
        f"[Git Log] Final branch used: {branch_name_acted_on=}, collection size={len(collection)}",
        extra={"repo_name": repo_name},
    )

    return collection


async def get_code_changes_for_collection(
    collection: CommitCollection, repo_path: str, repo_name: str
) -> CommitCollection:
    # Define a helper function to get the full code changes for each commit
    async def get_code_changes(commit_id):
        # Define the command to get the full changes for the specific commit
        commit_sha = str(commit_id) + "^!"
        command = ["git", "diff", commit_sha]

        try:
            process = await asyncio.create_subprocess_exec(
                *command, cwd=repo_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            result = Result(process.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore"))

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

    if not collection.is_empty():
        # Apply the helper function to each commit
        tasks = [get_code_changes(commit.id) for commit in collection.commits]
        code_changes = await asyncio.gather(*tasks)

        # Update commits with code changes
        for commit, code in zip(collection.commits, code_changes):
            commit.code = code

    return collection


def postprocess_collection(collection: CommitCollection) -> CommitCollection:
    if collection.is_empty():
        return collection

    # Remove commits with null code (equivalent to dropna)
    cleaned_commits = [commit for commit in collection.commits if commit.code is not None]

    return CommitCollection(commits=cleaned_commits)


def count_tokens_collection(collection: CommitCollection, column="code", model="gpt-3.5-turbo") -> CommitCollection:
    if collection.is_empty():
        return collection

    # Load the encoding for the specified model
    encoding = tiktoken.encoding_for_model(model)

    # Define a function to trim text for each record and calculate token count
    def trim_text_and_count(text):
        if text is None:
            return 0
        return len(encoding.encode(text)) + 1500

    # Apply the trimming and token counting function to each commit
    for commit in collection.commits:
        if column == "code":
            commit.tik_tokens = trim_text_and_count(commit.code)

    return collection


def filter_irrelevant_files_collection(collection: CommitCollection) -> CommitCollection:
    """Filter commits with irrelevant files using existing filter logic."""
    if collection.is_empty():
        return collection

    # Use the updated filter_irrelevant_files function with records
    records = collection.to_records()
    filtered_records = filter_irrelevant_files_records(records)

    # Convert back to CommitCollection
    filtered_commits = []
    for record in filtered_records:
        # Handle date conversion if needed
        if "date" in record and isinstance(record["date"], str):
            record["date"] = datetime.fromisoformat(record["date"]).date()
        filtered_commits.append(CommitData(**record))

    return CommitCollection(commits=filtered_commits)


def save_collection_to_csv(collection: CommitCollection, file_path) -> pd.DataFrame:
    if collection.is_empty():
        # Create empty CSV with headers
        df = pd.DataFrame(columns=list(CommitData.model_fields.keys()))
    else:
        df = pd.DataFrame(collection.to_records())

    df.to_csv(file_path, index=False)
    return df


@instrumented
async def gather_process_all_repos_data(
    main_folder_path,
    start_date,
    end_date,
    repos: list[str],
) -> CommitCollection:
    main_collection = CommitCollection()

    # Iterate over each folder in the main folder path
    for repo_name in os.listdir(main_folder_path):
        # Check if the repository is in the list of repositories to process
        if repo_name not in repos:
            continue

        repo_path = os.path.join(main_folder_path, repo_name)

        # Check if the path is a directory and contains a .git folder
        if os.path.isdir(repo_path) and ".git" in os.listdir(repo_path):
            logging.info(f"Processing repository: {repo_name}")
            repo_collection = await get_commit_data_as_collection(repo_path, repo_name, start_date, end_date)
            logging.info(f"getting code changes for: {repo_name}: with collection size {len(repo_collection)}")
            repo_collection = await get_code_changes_for_collection(repo_collection, repo_path, repo_name)
            logging.info(f"got code changes for: {repo_name}: with collection size {len(repo_collection)}")

            repo_collection = filter_irrelevant_files_collection(repo_collection)
            repo_collection = postprocess_collection(repo_collection)
            logging.info(
                f"size for repo: {repo_name}: after removing null rows and filtering by date: {len(repo_collection)}"
            )
            repo_collection = count_tokens_collection(repo_collection)
            logging.info(f"size for repo: {repo_name}: after trimming records: {len(repo_collection)}")

            # Append the repository data to the main collection, excluding empty collections
            if not repo_collection.is_empty():
                main_collection.commits.extend(repo_collection.commits)
        else:
            logging.info(f"Skipping {repo_name}: {repo_path} is not a git repository")

    return main_collection

import logging
import os
import re

logger = logging.getLogger(__name__)

IRRELEVANT_PATTERNS = [
    # Development and build artifacts
    r".*\.(log|tmp|cache|bak)$",
    r"build/",
    r"dist/",
    r"node_modules/",
    r"__pycache__/",
    r"\.gradle/",
    r"target/",
    r"cmake-build-.*",
    # Version control and IDE files
    r"\.git/",
    r"\.svn/",
    r"\.idea/",
    r"\.vscode/",
    r".*\.idea.*",
    r".*\.iml$",
    # Dependency and package management
    r"package-lock\.json",
    r"yarn\.lock",
    r"Podfile\.lock",
    r"composer\.lock",
    # Configuration files (often not core project logic)
    r".*\.config$",
    r".*\.ini$",
    r".*\.yaml$",
    r".*\.yml$",
    # Media and design files
    r".*\.(png|jpg|jpeg|gif|bmp|svg)$",
    r".*\.(mp3|mp4|wav|mov)$",
    # Documentation and misc
    r"LICENSE",
    r"CHANGELOG",
    r".*\.md$",
]

# Irrelevant extensions
IRRELEVANT_EXTENSIONS = [
    ".log",
    ".tmp",
    ".bak",
    ".lock",
    ".cache",
    ".idea",
    ".iml",
    ".DS_Store",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
    ".so",
    ".bin",
    ".obj",
    ".o",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".tar",
    ".gz",
    ".7z",
    ".lock",
]


def is_irrelevant_file(file_path: str) -> bool:
    # Check if file matches any irrelevance pattern
    if any(re.search(pattern, str(file_path), re.IGNORECASE) for pattern in IRRELEVANT_PATTERNS):
        logger.info(f"Irrelevant file: {file_path}")
        return True
    # Check file extension
    file_ext = os.path.splitext(str(file_path))[1]
    if file_ext in IRRELEVANT_EXTENSIONS:
        logger.info(f"Irrelevant file: {file_path}")
        return True
    return False


def filter_git_diff(code: str | None) -> str | None:
    """Filter out irrelevant file diffs from git diff output"""
    if not code or not isinstance(code, str):
        return code

    lines = code.split("\n")
    filtered_lines = []
    skip_current_file = False

    for line in lines:
        # Check for file header (diff --git a/file b/file)
        if line.startswith("diff --git"):
            # Extract filename from git diff header
            match = re.search(r"diff --git a/(.*?) b/", line)
            if match:
                current_file = match.group(1)
                skip_current_file = is_irrelevant_file(current_file)
            else:
                skip_current_file = False

        # Skip lines for irrelevant files
        if not skip_current_file:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def filter_files(file_paths: list[str]) -> list[str]:
    result = []
    for file_path in file_paths:
        if not is_irrelevant_file(file_path):
            result.append(file_path)

    return result


def filter_irrelevant_files_records(records):
    """Filter irrelevant files from a list of records (dictionaries)."""
    filtered_records = []

    for record in records:
        filtered_record = record.copy()

        # Filter out irrelevant files from 'files' column if it exists
        if "files" in filtered_record:
            filtered_record["files"] = filter_files(filtered_record["files"])

        # Filter git diff content from 'code' column if it exists
        if "code" in filtered_record:
            filtered_code = filter_git_diff(filtered_record["code"])
            filtered_record["code"] = filtered_code

            # Skip records with empty or None code after filtering
            if not filtered_code or filtered_code.strip() == "":
                continue

        filtered_records.append(filtered_record)

    # Print statistics
    total_files = len(records)
    removed_files = total_files - len(filtered_records)
    if total_files > 0:
        removal_percentage = removed_files / total_files * 100
    else:
        removal_percentage = 0

    logger.info(
        f"Total files: {total_files} Removed files: {removed_files} Removal percentage: {removal_percentage:.2f}%"
    )
    return filtered_records

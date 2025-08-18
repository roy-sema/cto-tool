import logging
from pathlib import Path

import chardet
import pandas as pd

# Setup logger
logger = logging.getLogger(__name__)

INTEGER_COLUMNS = [
    "tik_tokens",
    "Prompt_Tokens",
    "Completion_Tokens",
    "jira_tik_tokens",
    "summary_tik_token",
    "total_tik_token",
    "output_tik_tokens",
]


def detect_encoding(file_path: Path, sample_size: int = 10000) -> str:
    with open(file_path, "rb") as f:
        result = chardet.detect(f.read(sample_size))
    encoding = result["encoding"] or "utf-8"
    logger.info(f"Encoding detected {encoding}", extra={"encoding": encoding})
    return encoding


def check_datatype(df: pd.DataFrame):
    # Manually and strictly parse the date column
    if "date" in df.columns:
        # Strict parsing with the expected format
        df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise").dt.date

    # Manually and strictly parse the integer value columns
    for col in INTEGER_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="raise").astype(int)


def load_csv_safely(path: Path) -> pd.DataFrame:
    for encoding in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            df = pd.read_csv(path, encoding=encoding)
            logger.info(
                f"Successfully loaded CSV with encoding {encoding}",
                extra={"encoding": encoding},
            )
            check_datatype(df)
            return df
        except UnicodeDecodeError:
            logger.warning(
                f"Failed to read with encoding {encoding}",
                extra={"encoding": encoding},
            )

    try:
        encoding = detect_encoding(path)
        df = pd.read_csv(path, encoding=encoding)
        logger.info(
            f"Successfully loaded CSV with detected encoding {encoding}",
            extra={"encoding": encoding},
        )
    except UnicodeDecodeError:
        logger.exception("Failed to read CSV after encoding detection")
        raise
    check_datatype(df)
    return df

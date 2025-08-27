import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

import anthropic
import pandas as pd
import tiktoken
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda
from otel_extensions import instrumented
from rest_framework import status

from contextualization.conf.config import conf, get_config, llm_name
from contextualization.conf.get_llm import get_llm

logger = logging.getLogger(__name__)

batch_threshold = conf["llms"][llm_name]["batch_threshold"]
token_limit = conf["llms"][llm_name]["token_limit"]

encoding_name = "gpt-3.5-turbo"
tokenizer = tiktoken.encoding_for_model(encoding_name)
llm = get_llm()


def get_batches(data: pd.DataFrame, tiktoken_column: str, prompt_token_length: int = 1500) -> list[pd.DataFrame]:
    """
    Create batches ensuring no batch exceeds the batch_threshold from config.
    Drop the tiktoken_column from the resulting batches.
    """
    try:
        data_copy = data.copy()

        # Always use tiktoken_column for individual token counts
        individual_token_counts = data_copy[tiktoken_column] + prompt_token_length

        dataframes = []
        current_batch_tokens = 0
        current_batch_indices = []

        # Process each row one by one
        for idx, token_count in enumerate(individual_token_counts):
            if current_batch_tokens + token_count > batch_threshold and current_batch_indices:
                batch = data_copy.iloc[current_batch_indices]
                dataframes.append(batch)
                current_batch_tokens = token_count
                current_batch_indices = [idx]
            else:
                current_batch_tokens += token_count
                current_batch_indices.append(idx)

        # Add the final batch if not empty
        if current_batch_indices:
            batch = data_copy.iloc[current_batch_indices]
            dataframes.append(batch)

        logger.info(
            f"Split data into {len(dataframes)} batches using token column {tiktoken_column} and threshold {batch_threshold}"
        )
        return dataframes

    except Exception:
        logger.exception(
            f"Error creating batches using token column",
            extra={"tiktoken_colum": tiktoken_column},
        )
        return []


async def count_tokens(input_values: list[str]) -> list[int]:
    # Create tasks only for valid string inputs
    tasks = []
    valid_indices = []

    for idx, input_value in enumerate(input_values):
        if isinstance(input_value, str) and input_value.strip():
            tasks.append(llm.aget_num_tokens_from_messages([BaseMessage(content=input_value, type="human")]))
            valid_indices.append(idx)

    if not tasks:
        return [0] * len(input_values)

    token_counts = await asyncio.gather(*tasks, return_exceptions=True)

    # Build result array with zeros for invalid inputs and actual counts for valid ones
    result = [0] * len(input_values)
    for i, idx in enumerate(valid_indices):
        if isinstance(token_counts[i], Exception):
            logger.exception("Error while calculating token count")
            result[idx] = 0
        else:
            result[idx] = token_counts[i]

    return result


@instrumented(span_name="calculate_token_count")
async def calculate_token_count_async(
    df,
    text_columns: list[str] | None = None,
    token_column="summary_tik_token",
):
    """
    Calculates the total number of tokens across multiple text columns and stores it in a new column.

    Args:
        df (pd.DataFrame): The DataFrame containing the text columns.
        text_columns (list): List of column names with text to tokenize. Default is ['Summary'].
        token_column (str): The name of the new column to store total token counts. Default is 'summary_tik_token'.

    Returns:
        pd.DataFrame: The DataFrame with an additional column for total token counts.
    """
    if text_columns is None:
        text_columns = ["Summary"]

    if df.empty:
        error_msg = f"DataFrame is empty for calculating the token count. Stopping the process."
        raise ValueError(error_msg)

    logger.info(f"Calculating token count for {len(text_columns)} columns")

    # Check which columns actually exist in the dataframe
    available_columns = [col for col in text_columns if col in df.columns]

    if not available_columns:
        error_msg = f"None of the specified columns exist in the DataFrame."
        raise ValueError(error_msg)

    # Initialize token column with zeros
    df[token_column] = 0

    # Calculate and add token counts for each column
    for column in available_columns:
        # Skip non-string columns to avoid tokenization issues
        if df[column].dtype != "object" and not df[column].dtype.name.startswith("str"):
            continue

        # Process each column individually
        column_inputs = df[column].fillna("").astype(str)
        token_count = await count_tokens(column_inputs.to_list())

        df[token_column] += token_count

    logger.info(f"Token counting completed. Column '{token_column}' contains the total token counts.")
    return df


def get_batches_to_merge(
    data: pd.DataFrame, tiktoken_column: str, prompt_token_length: int = 1500
) -> list[pd.DataFrame]:
    """
    Create batches that are going to be merged into a single API call to the LLM.
    A single call has to fit into the context window of the LLM.
    """
    logger.info("Creating chunks from the data")

    try:
        dataframes = []
        start_idx = 0
        while start_idx < len(data):
            cumulative_sum = data[tiktoken_column].iloc[start_idx:].cumsum()
            # A single API call has to fit into the context window of the LLM
            # Take into account also that the prompt has a certain number of tokens
            end_idx = cumulative_sum[cumulative_sum >= (token_limit - prompt_token_length)].index
            if len(end_idx) > 0:
                end_idx = end_idx[0]
            else:
                end_idx = len(data) - 1
            batch = data.iloc[start_idx : end_idx + 1]
            dataframes.append(batch)
            start_idx = end_idx + 1

        return dataframes

    except Exception:
        logger.exception(f"Error while creating chunks")
        return []


async def async_chain_call(chain: Runnable, input_dict: dict) -> Any:
    return await asyncio.to_thread(chain.invoke, input_dict)


async def run_async_batch(chain: Runnable, batches: list[dict]) -> list[Any]:
    # gemini needs different handling of batches
    tasks = [async_chain_call(chain, b) for b in batches]
    return await asyncio.gather(*tasks)


async def truncate_input(inputs: dict) -> dict:
    for input_key in inputs:
        input_value = inputs[input_key]
        if input_value is None or not isinstance(input_value, str):
            continue

        # Skip empty string
        if not input_value.strip():
            continue

        # Use actual token counting instead of character estimation
        messages = [BaseMessage(content=input_value, type="human")]
        try:
            tokens = await llm.aget_num_tokens_from_messages(messages)
        except Exception:
            logger.exception("Error while calculating token count")
            tokens = 0

        excess = tokens - token_limit

        # Trimming prompt until it fits into limit by Anthropic token calculation
        while excess > 0:
            percentage_to_leave = (token_limit / tokens) - 0.01  # 1% to be safe
            cut_pos = int(len(input_value) * percentage_to_leave)
            input_value = input_value[:cut_pos]

            messages = [BaseMessage(content=input_value, type="human")]
            tokens = await llm.aget_num_tokens_from_messages(messages)
            excess = tokens - token_limit

        inputs[input_key] = input_value

    return inputs


def truncate_input_gemini(inputs: dict) -> dict:
    gemini = get_llm(big_text=True)
    config = get_config(big_text=True)
    for input_key in inputs:
        input_value = inputs[input_key]
        if input_value is None or not isinstance(input_value, str):
            continue

        # Skip empty string
        if not input_value.strip():
            continue

        # Use actual token counting instead of character estimation
        try:
            tokens = gemini.get_num_tokens(input_value)
        except Exception:
            logger.exception("Error while calculating token count")
            tokens = 0
        excess = tokens - config.token_limit

        # Trimming prompt until it fits into limit by Anthropic token calculation
        while excess > 0:
            percentage_to_leave = (config.token_limit / tokens) - 0.01  # 1% to be safe
            cut_pos = int(len(input_value) * percentage_to_leave)
            input_value = input_value[:cut_pos]

            tokens = gemini.get_num_tokens(input_value)
            excess = tokens - config.token_limit

        inputs[input_key] = input_value

    return inputs


def get_input_runnable(
    big_text: bool = False,
) -> RunnableLambda[dict, Coroutine[Any, Any, dict]] | None:
    if big_text:
        return RunnableLambda(truncate_input_gemini)

    return RunnableLambda(truncate_input)


async def separate_big_inputs(inputs: list[dict]) -> tuple[list[dict], list[dict]]:
    big_inputs = []
    small_inputs = []

    config = get_config(big_text=False)
    for input_dict in inputs:
        token_count = 0
        for input_key, input_value in input_dict.items():
            if input_value is None or not isinstance(input_value, str):
                continue

            # Skip empty string
            if not input_value.strip():
                continue

            # Use actual token counting instead of character estimation
            messages = [BaseMessage(content=input_value, type="human")]
            try:
                tokens = await llm.aget_num_tokens_from_messages(messages)
            except anthropic.APIStatusError as status_error:
                tokens = 0
                if status_error.status_code in (status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, status.HTTP_400_BAD_REQUEST):
                    tokens = config.token_limit

            token_count = token_count + tokens

        if token_count > config.token_limit:
            big_inputs.append(input_dict)
        else:
            small_inputs.append(input_dict)

    return small_inputs, big_inputs

import asyncio
import logging
import os
from pathlib import Path

import pandas as pd
from otel_extensions import instrumented

from contextualization.pipelines.anomaly_driven_insights.prompts.prompt import (
    diff_anomaly_analyser_chain,
    diff_anomaly_analyser_chain_big_text,
)
from contextualization.tools.llm_tools import run_async_batch, separate_big_inputs

logger = logging.getLogger(__name__)


# Git diff SUMMARY
# TODO: Not really sure this works as expected
@instrumented
async def find_anomalies_in_git_diffs(
    df_lists: list[pd.DataFrame],
    output_path: str | Path,
    error_log_path: str | Path,
) -> pd.DataFrame | None:
    if os.path.exists(output_path):
        logger.info("removing previous csv files non error batches as it exists")
        os.remove(output_path)
    if os.path.exists(error_log_path):
        logger.info("removing previous csv files for error batches as it exists")
        os.remove(error_log_path)
    logger.info("generating anomaly summaries from git diff code")

    task = """Analyze the provided git diff code to extract 0-3 significant highlights that represent notable changes rather than normal routine modifications. Focus on identifying substantial code improvements, architectural changes, performance optimizations, security enhancements, and critical bug fixes. Distinguish between normal development activities and true anomalies or innovations that would be relevant for executive reporting. These highlights will serve as the foundation for identifying anomaly insights in development patterns and risk areas."""

    async def analyze_change_with_token_callback(batch_content):
        results_with_tokens = []
        inputs = [{"diff_file": diff, "task": task} for diff in batch_content]
        tasks = []
        small_inputs, big_inputs = await separate_big_inputs(inputs)
        if small_inputs:
            tasks.append(diff_anomaly_analyser_chain.abatch(small_inputs))

        if big_inputs:
            tasks.append(run_async_batch(diff_anomaly_analyser_chain_big_text, big_inputs))
        outputs = await asyncio.gather(*tasks)
        outputs = [item for sublist in outputs for item in sublist]
        for output in outputs:
            if output is not None:
                result = {
                    "Completion_Tokens": output.usage_metadata.get("total_tokens", 0),
                    "anomaly_summary": output.content,
                }
            results_with_tokens.append(result)
        return results_with_tokens

    all_success_batches = []
    # Process the DataFrame in batches
    for batch in df_lists:
        # Ensure the 'code' column exists
        if "code" not in batch.columns:
            raise ValueError("The DataFrame must contain a 'code' column.")
        error_records = []
        # Apply the analysis to each 'code' entry in the batch with error handling
        batch_results = await analyze_change_with_token_callback(batch["code"].tolist())

        # Convert batch_results to a Series to use .isna()
        batch_results_series = pd.Series(batch_results)
        # Separate successful and errored results
        success_results = [res for res in batch_results if res is not None]
        error_indices = batch.index[batch_results_series.isna()]
        # Convert the results to DataFrames with the same index as the batch
        if success_results:
            success_df = pd.DataFrame(success_results, index=batch.index[: len(success_results)])
            updated_batch = batch.merge(success_df, left_index=True, right_index=True)
            all_success_batches.append(updated_batch)
            # Append the updated batch incrementally to the output CSV
            updated_batch.to_csv(
                output_path,
                mode="a",
                header=not os.path.exists(output_path),  # Only write the header for the first batch
                index=False,
            )

        # Append the original records that caused errors to error_records list
        if not error_indices.empty:
            # Collect error records for the current batch
            error_records = batch.loc[error_indices]
            error_records.to_csv(
                error_log_path,
                mode="a",
                index=False,
                header=not os.path.exists(error_log_path),
            )
    # Load and return the full, saved DataFrame with original and new columns
    if all_success_batches:
        return pd.concat(all_success_batches, ignore_index=True)
    else:
        logger.error(f"Git anomaly summary file not created", extra={"output_path": output_path})
        return None

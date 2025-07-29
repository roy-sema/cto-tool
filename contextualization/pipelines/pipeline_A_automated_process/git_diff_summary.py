import asyncio
import logging

import pandas as pd
from otel_extensions import instrumented

from contextualization.pipelines.pipeline_A_automated_process.prompts.prompt import (
    diff_analyser_chain,
    diff_analyser_chain_big_text,
)
from contextualization.tools.llm_tools import run_async_batch, separate_big_inputs


@instrumented
def analyze_code_changes(df_lists, output_path, error_log_path) -> pd.DataFrame | None:
    task = """Analyze the following `git diff` based on the system-level instructions. Provide the analysis in sections, 
    covering the summary, categorization, maintenance relevance, detailed analysis, intent, and whether the changes 
    are additive/enhancing or significant. Address potential bugs, code quality, test coverage, and any impact on dependencies.
    Add specific examples, such as repos or folders in the code, specific technologies, and libraries used.
    Even when there is a lot of data, pick out 1-2 specific anecdotes to illustrate your points. Mention the specific repository when you provide examples from files in the codebase.
    Keep the justification field short. If you do not find examples do not write: "it's not possible to mention specific repositories", or "no specific examples of repositories, folders, technologies, or libraries were provided in the given summary".
    """

    # Initialize common DataFrames for collecting all data
    all_successful_batches = []
    all_error_records = []

    async def analyze_change_with_token_callback(batch_content):
        results = []
        try:
            batch_content = batch_content.to_dict("records")
            inputs = [
                {
                    "diff": batch["code"],
                    "title": batch["commit_title"],
                    "description": batch["commit_description"],
                    "task": task,
                }
                for batch in batch_content
            ]
            tasks = []
            small_inputs, big_inputs = await separate_big_inputs(inputs)
            if small_inputs:
                tasks.append(diff_analyser_chain.abatch(small_inputs))

            if big_inputs:
                tasks.append(run_async_batch(diff_analyser_chain_big_text, big_inputs))

            outputs = await asyncio.gather(*tasks)
            outputs = [item for sublist in outputs for item in sublist]
            for output in outputs:
                results.append(output)
            return results
        except Exception:
            logging.exception("Pipeline A - Error processing batch")
            return [None] * len(batch_content)

    for batch in df_lists:
        if "code" not in batch.columns:
            raise ValueError("The DataFrame must contain a 'code' column.")
        batch_results = asyncio.run(analyze_change_with_token_callback(batch))

        batch_results_series = pd.Series(batch_results)
        success_results = [res for res in batch_results if res is not None]
        error_indices = batch.index[batch_results_series.isna()]
        if success_results:
            success_df = pd.DataFrame(success_results, index=batch.index[: len(success_results)])
            updated_batch = batch.merge(success_df, left_index=True, right_index=True)
            all_successful_batches.append(updated_batch)
        if not error_indices.empty:
            error_records = batch.loc[error_indices]
            all_error_records.append(error_records)

    # Write all successful results to file once at the end
    final_df = None
    if all_successful_batches:
        final_df = pd.concat(all_successful_batches, ignore_index=True)
        final_df.to_csv(output_path, index=False)

    if all_error_records:
        final_error_df = pd.concat(all_error_records, ignore_index=True)
        final_error_df.to_csv(error_log_path, index=False)
        logging.info(f"Successfully wrote {len(final_error_df)} error records to {error_log_path}")

    if all_successful_batches:
        return final_df
    else:
        logging.error("Pipeline A - No successful batches processed.")
        return None

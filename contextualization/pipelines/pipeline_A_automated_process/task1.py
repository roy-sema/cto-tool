import asyncio
import json
import logging

import pandas as pd

from contextualization.conf.config import conf, llm_name
from contextualization.pipelines.pipeline_A_automated_process.prompts.prompt2_task1 import (
    commit_analyser_chain,
)
from contextualization.tools.llm_tools import (
    calculate_token_count,
    get_batches_to_merge,
)

batch_threshold = conf["llms"][llm_name]["batch_threshold"]
token_limit = conf["llms"][llm_name]["token_limit"]


def analyze_commits_with_task(dfs):
    task = """Categorize and quantify the development work based on the changes made in different files and modules"""
    # Filter columns based on the task
    selected_columns = {
        "columns": [
            "Summary",
            "Categorization_of_Changes",
            "Maintenance_Relevance",
            "Description_of_Maintenance_Relevance",
            "Impact_on_product",
            "Purpose_of_change",
        ]
    }
    # Construct the schema with column names and rows
    column_names = " | ".join(dfs[0][selected_columns["columns"]].columns.to_list())
    chunks = []
    for df in dfs:
        row_str = "\n".join(
            df[selected_columns["columns"]].apply(lambda x: " | ".join(map(str, x)).replace("\n", " "), axis=1).values
        )
        chunks.append(row_str)
    logging.info(f"Total chunks to be processed: {len(chunks)}")
    outputs = []
    # Determine how many chunks to process per batch
    chunks_per_batch = max(1, batch_threshold // token_limit)

    # Assuming 'chunks' is a list of chunks to process
    for i in range(0, len(chunks), chunks_per_batch):
        # Select the current batch of chunks
        chunk_batch = chunks[i : i + chunks_per_batch]
        logging.info(f"Processing {len(chunk_batch)} chunk(s) out of total {len(chunks)}..")
        try:
            output = asyncio.run(
                commit_analyser_chain.abatch(
                    [{"csv_schema": column_names, "csv": chunk, "task": task} for chunk in chunk_batch]
                )
            )
            outputs.append(output)
        except Exception as e:
            logging.exception(f"Pipeline A - Error categorizing git diff record")
            continue
    return outputs


def categorize_and_quantify_development_work_from_summaries(
    df_git_summaries: pd.DataFrame,
    output_json_path,
):
    # Calculate the tik_tokens
    df_git_summaries = calculate_token_count(
        df_git_summaries,
        text_columns=[
            "Summary",
            "Description_of_Maintenance_Relevance",
            "Impact_on_product",
            "Purpose_of_change",
        ],
        token_column="output_tik_tokens",
    )

    # Split the DataFrame into chunks (assuming get_batches_to_merge function is defined)
    dfs = get_batches_to_merge(df_git_summaries, tiktoken_column="output_tik_tokens", prompt_token_length=8000)

    logging.info(
        f"Total amount of summaries to be processed: {len(dfs)}",
        extra={"batches_count": len(dfs), "batches_type": "commits_summary"},
    )

    output = analyze_commits_with_task(dfs)
    categorization_and_quantification_of_dev_work = [item for sublist in output for item in sublist]
    with open(output_json_path, "w") as file:
        json.dump(categorization_and_quantification_of_dev_work, file, indent=4)
    return categorization_and_quantification_of_dev_work


def count_changes_per_repository(df, output_json_path):
    # Count the number of changes per repository and category
    result = df.groupby(["repository", "Categorization_of_Changes"]).size().reset_index().rename(columns={0: "counts"})

    # Create a dictionary to store the counts per repository
    changes_dict = {}
    for repo in result["repository"].unique():
        changes_dict[repo] = {}
        repo_data = result[result["repository"] == repo]
        for _, row in repo_data.iterrows():
            category = row["Categorization_of_Changes"]
            count = row["counts"]
            logging.info(
                f"Changes count for {repo} and {category}: {count}",
                extra={"repo": repo, "category": category, "count": count},
            )
            changes_dict[repo][category] = count

    with open(output_json_path, "w") as file:
        json.dump(changes_dict, file, indent=4)
    logging.info("Changes per repository counted and saved successfully!")
    return changes_dict

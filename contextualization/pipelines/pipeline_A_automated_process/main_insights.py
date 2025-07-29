import json
import logging
from pathlib import Path

import pandas as pd
from otel_extensions import instrumented

from contextualization.pipelines.pipeline_A_automated_process.combining_summaries import (
    aggregate_summaries,
)
from contextualization.pipelines.pipeline_A_automated_process.prompts.refine_explanations import (
    refine_explanations_chain,
)
from contextualization.pipelines.pipeline_A_automated_process.task1 import (
    categorize_and_quantify_development_work_from_summaries,
)
from contextualization.tools.json_tools import round_percentages
from contextualization.utils.otel_utils import suppress_prompt_logging


def refine_final_json(updated_json, refine_explanations_chain):
    # Recursively go through the JSON and refine explanations
    def refine_fields(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ["justification", "examples", "summary"]:
                    data[key] = refine_explanations_chain.invoke({"input_text": data[key]})
                else:
                    refine_fields(value)

    # Update examples field if percentage is 0
    # Hypothesis: the JSON is structed like this (In two levels):
    # {
    # "maintenance_relevance": {
    #     "yes": {
    #         "percentage": x,
    #         "justification": "",
    #         "examples": ""
    #     },
    #     ...
    # },
    # "categories": {
    #     "tech_debt": {
    #         "percentage": x,
    #         "justification": "",
    #         "examples": ""
    #     },
    # ...
    def remove_examples_for_empty_category(data):
        for key1, value1 in data.items():  # first level
            if isinstance(value1, dict):
                for key2, value2 in value1.items():  # second level
                    if value2.get("percentage") == 0:
                        value2["examples"] = "No examples provided."

    logging.info("Refine text with LLM prompting")
    refine_fields(updated_json)
    logging.info("Remove examples for empty category")
    remove_examples_for_empty_category(updated_json)
    logging.info("Round percentages")
    round_percentages(updated_json, ["percentage"])

    return updated_json


@instrumented
def get_git_work_categorization_and_quantification(df: pd.DataFrame, output_dir, git_data_output_path):
    df = df.copy()  # just in case

    output_json = output_dir / f"{git_data_output_path.stem}_overall_summary.json"
    final_output_json_path = output_dir / f"{git_data_output_path.stem}_overall_summary_final.json"

    # Process the analysed summary using batch processing
    logging.info("Creating the batches by summarizing the summaries obtained")
    with suppress_prompt_logging():
        categorization_json = categorize_and_quantify_development_work_from_summaries(df, output_json)
    logging.info("Batches of summaries created")

    # Aggregate summaries and save the final JSON
    logging.info("Aggregating the batches of summaries into one file")
    updated_json = aggregate_summaries(categorization_json)
    logging.info("Aggregating the batches of summaries into one file DONE")

    logging.info("Refine final JSON")
    updated_json = refine_final_json(updated_json, refine_explanations_chain)

    logging.info("Saving main JSON file")
    with open(final_output_json_path, "w") as file:
        json.dump(updated_json, file, indent=4)

    logging.info(f"Analysis completed. Results saved in directory: {output_dir}")
    return updated_json


def run_pipeline_a_insights(git_data_path: str):
    logging.info(f"Running pipeline A insights with {git_data_path=}")
    if not git_data_path.endswith("_summary.csv"):
        raise ValueError("The git_data_path must end with '_summary.csv'")

    output_dir = Path(git_data_path).parent
    git_data_output_path = Path(git_data_path.replace("_summary", "") + ".csv")

    return get_git_work_categorization_and_quantification(
        pd.read_csv(git_data_output_path), output_dir, git_data_output_path
    )

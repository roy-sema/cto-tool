import asyncio
import logging
from collections import defaultdict

from contextualization.pipelines.pipeline_A_automated_process.prompts.summary_prompt import (
    summary_chain,
)


# Function to process JSON strings
def process_json_strings(categorization_json: list[dict]) -> tuple[dict, list[str], dict]:
    accumulated_data = defaultdict(lambda: defaultdict(lambda: {"percentage": 0, "justification": "", "examples": ""}))
    summary_texts = []
    counts = defaultdict(lambda: defaultdict(int))
    for data in categorization_json:
        summary_texts.append(data["summary"])

        for section in ("maintenance_relevance", "categories"):
            if section in data:
                for key, values in data[section].items():
                    accumulated_data[section][key]["percentage"] += values["percentage"]
                    counts[section][key] += 1
                    accumulated_data[section][key]["justification"] += (
                        f" ##$## {values['justification']}"
                        if accumulated_data[section][key]["justification"]
                        else values["justification"]
                    )
                    accumulated_data[section][key]["examples"] += (
                        f" ##$## {values['examples']}"
                        if accumulated_data[section][key]["examples"]
                        else values["examples"]
                    )

    return accumulated_data, summary_texts, counts


# Function to calculate averages and create final JSON
def calculate_averages_and_finalize(accumulated_data, counts, summary_texts):
    final_data = {
        "maintenance_relevance": {},
        "categories": {},
        "summary": " ##$## ".join(summary_texts),
    }

    for section, items in accumulated_data.items():
        for key, values in items.items():
            mean_percentage = round(values["percentage"] / counts[section][key], 2)
            final_data[section][key] = {
                "percentage": mean_percentage,
                "justification": values["justification"],
                "examples": values["examples"],
            }
    return final_data


# Function to split justifications and summaries into lists
def split_justifications_and_summaries(result_json):
    split_list = []
    for k in result_json["maintenance_relevance"].keys():
        split_list.append(result_json["maintenance_relevance"][k]["justification"].split(" ##$## "))
        split_list.append(result_json["maintenance_relevance"][k]["examples"].split(" ##$## "))
    for k in result_json["categories"].keys():
        split_list.append(result_json["categories"][k]["justification"].split(" ##$## "))
        split_list.append(result_json["categories"][k]["examples"].split(" ##$## "))
    split_list.append(result_json["summary"].split(" ##$## "))

    return split_list


# Function to combine summaries
def combine_summary(entire_list):
    return asyncio.run(summary_chain.abatch([{"list_of_summaries": lst} for lst in entire_list]))


# Function to update final JSON with combined summaries
def update_final_json_with_summaries(result_json, results):
    filtered_keys_mapping = [
        (top_key, sub_key)
        for top_key, sub_dict in result_json.items()
        if isinstance(sub_dict, dict)
        for sub_key in sub_dict
    ]
    logging.info(f"present keys: {filtered_keys_mapping}")

    # TODO: this should be done in a more robust way and readable way
    i_result = 0
    i_mapping = 0
    while i_result < len(results) - 1:
        (section, key) = filtered_keys_mapping[i_mapping]
        result_json[section][key]["justification"] = results[i_result]["response"]
        i_result += 1
        result_json[section][key]["examples"] = results[i_result]["response"]
        i_result += 1
        i_mapping += 1
    result_json["summary"] = results[-1]["response"]
    return result_json


def aggregate_summaries(categorization_json: list[dict]):
    accumulated_data, summary_texts, counts = process_json_strings(categorization_json)
    final_data = calculate_averages_and_finalize(accumulated_data, counts, summary_texts)
    logging.info("Calculation of averages across batches completed")

    list_of_summary_to_extract = split_justifications_and_summaries(final_data)
    logging.info("Extracted  summaries and justification to pass on LLM")
    results = combine_summary(list_of_summary_to_extract)
    logging.info("Combined summaries and justification")
    updated_final_data = update_final_json_with_summaries(final_data, results)
    logging.info("completed aggregation of summaries into one file")
    return updated_final_data

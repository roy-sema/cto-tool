import logging
from collections import defaultdict
from typing import Any

from contextualization.pipelines.pipeline_A_automated_process.prompts.summary_prompt import (
    summary_chain,
)


def process_json_strings(categorization_json: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    accumulated_data = defaultdict(lambda: defaultdict(lambda: {"percentage": 0, "justification": "", "examples": ""}))
    summary_texts = []
    counts = defaultdict(lambda: defaultdict(int))
    for data in categorization_json:
        summary_texts.append(data["summary"])

        section = "categories"
        for key, values in data[section].items():
            accumulated_data[section][key]["percentage"] += values["percentage"]
            counts[section][key] += 1
            accumulated_data[section][key]["justification"] += (
                f" ##$## {values['justification']}"
                if accumulated_data[section][key]["justification"]
                else values["justification"]
            )
            accumulated_data[section][key]["examples"] += (
                f" ##$## {values['examples']}" if accumulated_data[section][key]["examples"] else values["examples"]
            )

    return accumulated_data, summary_texts, counts


def calculate_averages_and_finalize(accumulated_data: dict, counts: dict, summary_texts: list[str]) -> dict[str, Any]:
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


def split_justifications_and_summaries(result_json: dict[str, Any]) -> list[list[str]]:
    split_list = []
    for k in result_json["categories"].keys():
        split_list.append(result_json["categories"][k]["justification"].split(" ##$## "))
        split_list.append(result_json["categories"][k]["examples"].split(" ##$## "))
    split_list.append(result_json["summary"].split(" ##$## "))

    return split_list


def update_final_json_with_summaries(result_json: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
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


async def aggregate_summaries(categorization_json: list[dict[str, Any]]):
    accumulated_data, summary_texts, counts = process_json_strings(categorization_json)
    final_data = calculate_averages_and_finalize(accumulated_data, counts, summary_texts)
    logging.info("Calculation of averages across batches completed")

    list_of_summary_to_extract = split_justifications_and_summaries(final_data)
    logging.info("Extracted  summaries and justification to pass on LLM")
    results = await summary_chain.abatch([{"list_of_summaries": lst} for lst in list_of_summary_to_extract])
    logging.info("Combined summaries and justification")
    updated_final_data = update_final_json_with_summaries(final_data, results)
    logging.info("completed aggregation of summaries into one file")
    return updated_final_data

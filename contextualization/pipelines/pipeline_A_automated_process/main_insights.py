import json
import logging
from pathlib import Path

from otel_extensions import instrumented

from contextualization.pipelines.pipeline_A_automated_process.combining_summaries import (
    aggregate_summaries,
)
from contextualization.pipelines.pipeline_A_automated_process.models import CommitCollection
from contextualization.pipelines.pipeline_A_automated_process.task1 import (
    categorize_and_quantify_development_work_from_summaries,
)
from contextualization.tools.json_tools import round_percentages
from contextualization.utils.otel_utils import suppress_prompt_logging


def refine_final_json(updated_json: dict) -> dict:
    def remove_examples_for_empty_category(data):
        for key1, value1 in data.items():  # first level
            if isinstance(value1, dict):
                for key2, value2 in value1.items():  # second level
                    if value2.get("percentage") == 0:
                        value2["examples"] = "No examples provided."

    logging.info("Remove examples for empty category")
    remove_examples_for_empty_category(updated_json)
    logging.info("Round percentages")
    round_percentages(updated_json, ("percentage",))

    return updated_json


@instrumented
async def get_git_work_categorization_and_quantification(
    git_summaries: CommitCollection, final_output_json_path: Path
) -> dict:
    logging.info("Creating the batches by summarizing the summaries obtained")
    with suppress_prompt_logging():
        categorization_json = await categorize_and_quantify_development_work_from_summaries(git_summaries)
    logging.info("Batches of summaries created")

    logging.info("Aggregating the batches of summaries into one file")
    updated_json = await aggregate_summaries(categorization_json)
    logging.info("Aggregating the batches of summaries into one file DONE")

    logging.info("Refine final JSON")
    updated_json = refine_final_json(updated_json)

    logging.info("Saving main JSON file")
    with open(final_output_json_path, "w") as file:
        json.dump(updated_json, file, indent=4)

    return updated_json

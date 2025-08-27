import json
import logging
import os
from typing import TYPE_CHECKING

from contextualization.pipelines.insights_aggregation_pipeline.prompts.aggregate_anomalies_prompt import (
    aggregate_anomaly_chain,
)
from contextualization.pipelines.insights_aggregation_pipeline.prompts.summary_prompt import (
    summary_chain,
)
from contextualization.utils.vcr_mocks import calls_context

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from mvp.services.contextualization_service import ContextualizationResults


def add_unique_ids_to_insights(file_paths: list[str], contextualization_results: "ContextualizationResults") -> dict:
    """
    Add unique IDs to each insight in the insights_data dictionary for each input file.
    The prefix of the ID is determined based on whether 'jira' or 'git' is in the filename.

    Args:
        file_paths (list): List of paths to JSON files containing 'anomaly_insights'
        contextualization_results: Contextualization results.

    Returns:
        dict: A dictionary with filenames as keys and updated data as values.
    """
    git_anomaly_file = file_paths[0]
    jira_anomaly_file = file_paths[1] if len(file_paths) > 1 else None
    results = {}

    if contextualization_results.pipeline_anomaly_insights_result:
        logger.info(f"Adding the unique ids for anomaly insights in anomaly_insights pipieline result")
        for i, insight in enumerate(contextualization_results.pipeline_anomaly_insights_result.anomaly_insights):
            insight.unique_id = f"GIT_AN_{i + 1:02d}"

        with open(git_anomaly_file, "w") as file:
            json.dump(contextualization_results.pipeline_anomaly_insights_result.model_dump(), file, indent=4)

        results[git_anomaly_file] = contextualization_results.pipeline_anomaly_insights_result

    if contextualization_results.pipeline_jira_anomaly_insights_result and jira_anomaly_file:
        logger.info(f"Adding the unique ids for anomaly insights in jira_anomaly_insights pipieline result")
        for i, insight in enumerate(
            contextualization_results.pipeline_jira_anomaly_insights_result.skip_meeting_insights.anomaly_insights
        ):
            insight.unique_id = f"JIRA_AN_{i + 1:02d}"

        with open(jira_anomaly_file, "w") as file:
            json.dump(
                contextualization_results.pipeline_jira_anomaly_insights_result.skip_meeting_insights.model_dump(),
                file,
                indent=4,
            )

        results[jira_anomaly_file] = (
            contextualization_results.pipeline_jira_anomaly_insights_result.skip_meeting_insights
        )

    return results


async def aggregate_anomalies(
    input_files: list[str], output_path: str, contextualization_results: "ContextualizationResults"
) -> dict:
    """
    Aggregate anomaly and risk insights from multiple JSON files by grouping similar insights.

    Args:
        input_files (List[str]): List of input JSON file paths containing anomaly and risk insights.
        output_path (str): Path where the aggregated JSON output should be saved.
        contextualization_results: Contextualization results.

    Returns:
        Aggregated JSON saved to output_path
    """
    all_anomaly_insights = []
    models = [contextualization_results.pipeline_anomaly_insights_result]
    if contextualization_results.pipeline_jira_anomaly_insights_result:
        models.append(contextualization_results.pipeline_jira_anomaly_insights_result.skip_meeting_insights)

    # Load data from all input files
    for file_path, model in zip(input_files, models):
        all_anomaly_insights.extend(model.anomaly_insights)

    # Initialize the final JSON structure
    new_json = {"groups_of_insights": []}

    async def process_insights(insight_type: str, insights):
        """
        Helper function to process a specific type of insights (anomaly or risk).
        """
        if not insights:
            logger.info(f"No '{insight_type}' found in data.")
            return None

        formatted_insights = [
            {
                "unique_id": i.unique_id,
                "insight": i.insight,
                "title": i.title,
                "evidence": i.evidence,
                "category": i.category,
            }
            for i in insights
        ]

        result = await aggregate_anomaly_chain.ainvoke({"insights": formatted_insights})
        for group in result.get("similar_insights", []):
            details = []
            for sid in group.get("similar_insight_ids", []):
                matched = next((entry for entry in insights if entry.unique_id == sid), None)
                if matched:
                    details.append(matched.model_dump())
            # Add the details into the group
            group["details_of_insights"] = details
            # Append this group into the main 'groups_of_insights' list
            new_json["groups_of_insights"].append(group)

        logger.info(
            f"Finished processing {insight_type}. Total groups formed: {len(result.get('similar_insights', []))}"
        )

    # Process collected anomaly and risk insights
    logger.info("Processing similar anomaly insights")
    await process_insights("anomaly_insights", all_anomaly_insights)

    with open(output_path, "w") as file:
        json.dump(new_json, file, indent=4)
    logger.info(f"Aggregated insights saved to: {output_path}")

    return new_json


async def summarize_details(insights_json_path: str, data: dict) -> dict:
    result = await summary_chain.ainvoke({"insights": data})
    data.update(result)
    with open(insights_json_path, "w") as file:
        json.dump(data, file, indent=4)
    logger.info(f"Summarized insights saved to: {insights_json_path}")

    return data


async def run_insights_aggregation_pipeline(
    input_files: list[str],
    contextualization_results: "ContextualizationResults",
    output_folder: str | None = None,
) -> dict:
    logger.info(f"Running insights aggregation pipeline with params: {input_files=} {output_folder=}")

    with calls_context("insights_aggregation_pipeline.yaml"):
        # Use directory of first input file if output_folder is not provided
        if not output_folder:
            output_folder = os.path.dirname(input_files[0])

        # Ensure the output folder exists
        os.makedirs(output_folder, exist_ok=True)

        # Define the output path
        output_path = os.path.join(output_folder, "aggregated_anomaly_insights.json")

        add_unique_ids_to_insights(input_files, contextualization_results)
        aggregated_anomalies = await aggregate_anomalies(input_files, output_path, contextualization_results)
        return await summarize_details(output_path, aggregated_anomalies)

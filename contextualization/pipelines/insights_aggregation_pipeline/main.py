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

if TYPE_CHECKING:
    from mvp.services.contextualization_service import ContextualizationResults


def add_unique_ids_to_insights(file_paths, contextualization_results: "ContextualizationResults"):
    """
    Add unique IDs to each insight in the insights_data dictionary for each input file.
    The prefix of the ID is determined based on whether 'jira' or 'git' is in the filename.

    Args:
        file_paths (list): List of paths to JSON files containing 'anomaly_insights' and 'risk_insights' lists.
        contextualization_results: Contextualization results.

    Returns:
        dict: A dictionary with filenames as keys and updated data as values.
    """
    results = {}
    models = [contextualization_results.pipeline_anomaly_insights_result]
    if contextualization_results.pipeline_jira_anomaly_insights_result:
        models.append(contextualization_results.pipeline_jira_anomaly_insights_result.skip_meeting_insights)

    for file_path, model in zip(file_paths, models):
        filename_lower = os.path.basename(file_path).lower()
        if "jira" in filename_lower:
            anomaly_prefix = "JIRA"
        elif "git" in filename_lower:
            anomaly_prefix = "GIT"
        else:
            anomaly_prefix = "GEN"  # fallback generic prefix

        logging.info(f"Adding the unique ids for anomaly insights in {file_path}")
        for i, insight in enumerate(model.anomaly_insights):
            insight.unique_id = f"{anomaly_prefix}_AN_{i + 1:02d}"

        logging.info(f"Adding the unique ids for risk insights in {file_path}")
        for i, insight in enumerate(model.risk_insights):
            insight.unique_id = f"{anomaly_prefix}_RK_{i + 1:02d}"

        with open(file_path, "w") as file:
            json.dump(model.model_dump(), file, indent=4)

        results[file_path] = model

    return results


def aggregate_anomalies(input_files: list[str], output_path: str, contextualization_results):
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
    all_risk_insights = []
    models = [contextualization_results.pipeline_anomaly_insights_result]
    if contextualization_results.pipeline_jira_anomaly_insights_result:
        models.append(contextualization_results.pipeline_jira_anomaly_insights_result.skip_meeting_insights)

    # Load data from all input files
    for file_path, model in zip(input_files, models):
        all_anomaly_insights.extend(model.anomaly_insights)
        all_risk_insights.extend(model.risk_insights)

    # Initialize the final JSON structure
    new_json = {"groups_of_insights": []}

    def process_insights(insight_type: str, insights):
        """
        Helper function to process a specific type of insights (anomaly or risk).
        """
        if not insights:
            logging.info(f"No '{insight_type}' found in data.")
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

        try:
            result = aggregate_anomaly_chain.invoke({"insights": formatted_insights})
        except Exception:
            logging.exception(
                "Pipeline insight aggregation - Error generating results",
                extra={"insight_type": insight_type},
            )
            return

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

        logging.info(
            f"Finished processing {insight_type}. Total groups formed: {len(result.get('similar_insights', []))}"
        )

    # Process collected anomaly and risk insights
    logging.info("Processing similar anomaly insights")
    process_insights("anomaly_insights", all_anomaly_insights)
    logging.info("Processing similar risk insights")
    process_insights("risk_insights", all_risk_insights)

    # Write the final aggregated output
    try:
        with open(output_path, "w") as file:
            json.dump(new_json, file, indent=4)
        logging.info(f"Aggregated insights saved to: {output_path}")
    except Exception:
        logging.exception("Pipeline insight aggregation - Error writing to output file")

    return new_json


def summarize_details(insights_json_path, data):
    # Invoke summary chain
    try:
        result = summary_chain.invoke({"insights": data})
    except Exception:
        logging.exception("Pipeline insight aggregation - Error generating summary")
        return

    # Append the 'summary' to results
    data.update(result)

    # Write the results back to file
    try:
        with open(insights_json_path, "w") as file:
            json.dump(data, file, indent=4)
        logging.info(f"Summarized insights saved to: {insights_json_path}")
    except Exception:
        logging.exception("Pipeline insight aggregation - Error writing to output file")

    return data


def run_insights_aggregation_pipeline(
    input_files: list[str],
    contextualization_results: "ContextualizationResults",
    output_folder: str | None = None,
):
    logging.info(f"Running insights aggregation pipeline with params: {input_files=} {output_folder=}")

    with calls_context("insights_aggregation_pipeline.json"):
        # Use directory of first input file if output_folder is not provided
        if not output_folder:
            output_folder = os.path.dirname(input_files[0])

        # Ensure the output folder exists
        os.makedirs(output_folder, exist_ok=True)

        # Define the output path
        output_path = os.path.join(output_folder, "aggregated_anomaly_insights.json")

        add_unique_ids_to_insights(input_files, contextualization_results)
        aggregated_anomalies = aggregate_anomalies(input_files, output_path, contextualization_results)
        return summarize_details(output_path, aggregated_anomalies)

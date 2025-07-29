import asyncio
import json
import logging
from pathlib import Path

import pandas as pd
from otel_extensions import instrumented
from pydantic import ValidationError

from contextualization.conf.config import conf, llm_name
from contextualization.models.anomaly_insights import JiraCombinedInsights, JiraInsight
from contextualization.pipelines.anomaly_driven_insights.main import execute_concurrently
from contextualization.pipelines.insights_aggregation_pipeline.schemas import SkipMeetingInsights
from contextualization.pipelines.jira_anomaly_driven_insights.batching_issues import (
    get_jira_issues_batches,
)
from contextualization.pipelines.jira_anomaly_driven_insights.prompts.jira_anomaly_prompt import (
    anomaly_ranking_chain,
    jira_anomaly_analysis_chain,
    jira_anomaly_analysis_summary_chain,
    skip_meeting_analysis_chain,
)
from contextualization.utils.vcr_mocks import calls_context

logger = logging.getLogger(__name__)


token_limit = conf["llms"][llm_name]["token_limit"]
batch_threshold = conf["llms"][llm_name]["batch_threshold"]

# Define required columns
REQUIRED_COLUMNS = [
    "issue_key",
    "parsed_changelog",
    "summary",
    "Issue Type",
    "created",
    "description",
    "priority",
    "labels",
    "assignee",
    "updated",
    "status",
    "stage_category",
    "llm_category",
]


def validate_dataframe(df):
    """
    Validate the dataframe to ensure it has the required columns.

    Args:
        df (pd.DataFrame): DataFrame to validate

    Returns:
        tuple: (is_valid, missing_columns)
    """
    if df.empty:
        return False, ["DataFrame is empty"]

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    is_valid = len(missing_columns) == 0

    return is_valid, missing_columns


def extract_project_from_issue_key(issue_key):
    """
    Extract project name from issue key (e.g., 'CON-110' -> 'CON')
    """
    if pd.isna(issue_key) or not isinstance(issue_key, str):
        return "UNKNOWN"
    parts = issue_key.split("-")
    if len(parts) > 0:
        return parts[0]
    return "UNKNOWN"


def add_ticket_categories_post_process(insights_json, jira_data_df: pd.DataFrame):
    """
    Post-process insights to add correct ticket categories by looking up CSV data.

    Args:
        insights_json (dict): The insights JSON with anomaly_insights and risk_insights
        jira_data_df: (DataFrame): Dataframe with ticket data

    Returns:
        dict: Updated insights JSON with correct ticket_categories
    """
    logger.info("Starting ticket category post-processing")

    df = jira_data_df

    total_insights_processed = 0
    total_categories_added = 0

    # Process both anomaly and risk insights
    for insight_type in ["anomaly_insights", "risk_insights"]:
        insight_list = insights_json[insight_type]

        for idx, insight in enumerate(insight_list):
            try:
                # Get ticket IDs directly from source field
                ticket_ids = insight["source"]

                logger.debug(f"Processing {insight_type}[{idx}]: Found ticket IDs: {ticket_ids}")

                # Look up categories in CSV
                categories = set()

                for ticket_id in ticket_ids:
                    try:
                        # Find the row with matching issue_key
                        mask = df["issue_key"] == ticket_id
                        if mask.any():
                            category_value = df.loc[mask, "llm_category"].iloc[0]
                            if pd.notna(category_value) and str(category_value).strip():
                                category_clean = str(category_value).strip()
                                categories.add(category_clean)
                                logger.debug(f"  {ticket_id} -> {category_clean}")
                            else:
                                logger.debug(f"  {ticket_id} -> Empty/NaN category")
                        else:
                            logger.debug(f"  {ticket_id} -> NOT FOUND in CSV")
                    except Exception as e:
                        logger.exception("Error processing ticket", extra={"ticket_id": ticket_id})

                # Update only the ticket_categories field
                insight["ticket_categories"] = sorted(list(categories))

                total_insights_processed += 1
                total_categories_added += len(categories)

                logger.debug(f"  Final categories: {insight['ticket_categories']}")

            except Exception as e:
                logger.exception(
                    "Error processing insight",
                    extra={"insight_type": insight_type, "index": idx},
                )
                # Ensure the insight has the required fields even if processing fails
                if "ticket_categories" not in insight:
                    insight["ticket_categories"] = []

    logger.info(
        f"Post-processing complete: {total_insights_processed} insights processed, {total_categories_added} total categories added"
    )
    return insights_json


@instrumented
async def find_insights_and_risks_in_jira_tickets(combined_text_batches: list[str]):
    results = []
    try:
        input_list = [{"jira_data": chunk} for chunk in combined_text_batches]
        results = await jira_anomaly_analysis_chain.abatch(input_list)
    except Exception:
        logging.exception("Pipeline Jira anomalies - Error analyzing batch")

    return results


@instrumented
def rank_jira_insights(insights_list):
    """
    Rank insights based on importance using anomaly_ranking_chain.
    Only changes the order of insights, preserves all original data.
    Following Git ranking approach.

    Args:
        insights_list (list): List of insights to rank

    Returns:
        list: Ranked list of insights with all original fields and structure
    """
    if not insights_list:
        return []

    logging.info(f"Ranking {len(insights_list)} insights by criticality")

    # Prepare data for ranking - following Git approach format
    ranking_input = []
    for item in insights_list:
        ranking_input.append(
            {
                "repo": item.get("project", "UNKNOWN"),
                "critical_anomaly": item.get("insight", ""),  # Use insight field for critical_anomaly
            }
        )

    # Attempt to rank with retries
    # Invoke the ranking chain
    ranked_items = anomaly_ranking_chain.invoke({"analysis_content": ranking_input})

    if isinstance(ranked_items, dict) and "critical_anomalies" in ranked_items:
        logging.info("Successfully ranked insights")

        # Create a new ranked list with all original fields
        ranked_list = []
        for ranked_item in ranked_items["critical_anomalies"]:
            # Find matching original item to preserve all fields
            for orig_item in insights_list:
                if (
                    orig_item.get("project", "UNKNOWN") == ranked_item["repo"]
                    and orig_item.get("insight", "") == ranked_item["critical_anomaly"]
                ):
                    ranked_list.append(orig_item)
                    break

        return ranked_list
    else:
        logging.warning(f"Unexpected response format from ranking chain: {type(ranked_items)}")

    # If ranking fails after all retries, return original list
    logging.warning("Could not rank insights after multiple attempts, returning original list")
    return insights_list


@instrumented
async def summarize_insights_for_project(project_results, project_name, output_dir, jira_data_df: pd.DataFrame):
    """
    Summarize anomaly and risk insights for a project across all batches.

    Args:
        project_results (list): List of batch results for the project
        project_name (str): Name of the project
        output_dir (Path): Path to save output files
        jira_data_df: (DataFrame): Jira data frame

    Returns:
        dict: Summarized results for this project
    """
    logging.info(f"Summarizing insights for project: {project_name} across {len(project_results)} batches")

    # Define output path for summarized results
    output_summary_path = output_dir / f"{project_name}_summary_jira_anomalies.json"

    try:
        # Convert the project results to a JSON string for the LLM
        project_results_str = json.dumps(project_results)

        logging.info(f"Analyzing and summarizing {project_name} data...")

        # Invoke the summary chain
        summarized_result = await jira_anomaly_analysis_summary_chain.ainvoke({"jira_data": project_results_str})

        # POST-PROCESS: Add correct ticket categories
        logging.info(f"Post-processing ticket categories for {project_name}")
        summarized_result = add_ticket_categories_post_process(summarized_result, jira_data_df)

        # Add project name to each insight for ranking purposes
        if "anomaly_insights" in summarized_result:
            for insight in summarized_result["anomaly_insights"]:
                insight["project"] = project_name

        if "risk_insights" in summarized_result:
            for insight in summarized_result["risk_insights"]:
                insight["project"] = project_name

        # Rank the anomaly and risk insights
        if "anomaly_insights" in summarized_result and summarized_result["anomaly_insights"]:
            summarized_result["anomaly_insights"] = rank_jira_insights(summarized_result["anomaly_insights"])

        if "risk_insights" in summarized_result and summarized_result["risk_insights"]:
            summarized_result["risk_insights"] = rank_jira_insights(summarized_result["risk_insights"])

        # Add project metadata
        summarized_result["project"] = project_name
        summarized_result["batch_count"] = len(project_results)

        logging.info(
            f"Created summary with {len(summarized_result.get('anomaly_insights', []))} anomaly insights and {len(summarized_result.get('risk_insights', []))} risk insights"
        )

        # Save the summarized results
        with open(output_summary_path, "w") as f:
            json.dump(summarized_result, f, indent=2)

        logging.info(f"Saved summarized results to {output_summary_path}")

        return summarized_result

    except Exception:
        logging.exception(
            "Pipeline Jira anomalies - Error summarizing insights",
            extra={"project_name": project_name},
        )
        return None


@instrumented
async def find_jira_insights_in_project(project_name, project_df, output_dir):
    """
    Process data for a specific project and save results.

    Args:
        project_name (str): Name of the project
        project_df (pd.DataFrame): DataFrame containing project data
        output_dir (Path): Path to save output files

    Returns:
        list: List of results for this project
    """
    logging.info(f"Processing project: {project_name} with {len(project_df)} records")

    # Define output paths for this project
    base_filename = f"{project_name}_anomaly_analysis"
    output_json_path = output_dir / f"{project_name}_anomaly_insight.json"
    error_log_path = output_dir / f"{base_filename}_error.csv"

    project_results = []

    try:
        # Get batches using the imported function
        df_batches = await get_jira_issues_batches(project_df)

        # Analyze the batches
        project_results = await find_insights_and_risks_in_jira_tickets(df_batches)

        # Include the project_name in results
        if project_results is not None:
            project_results = [
                ({**result, "project": project_name} if isinstance(result, dict) else result)
                for result in project_results
            ]

        # Saved the output results
        with open(output_json_path, "w") as f:
            json.dump(project_results, f, indent=2)

        logging.info(f"Analysis completed for project {project_name} with {len(project_results)} batch results")

    except Exception:
        logging.exception(
            "Pipeline Jira anomalies - Error processing JIRA data for project",
            extra={"project_name": project_name},
        )

    return project_results


@instrumented
def combine_all_project_summaries_and_rank_insights(all_summaries, output_dir, jira_data_df: pd.DataFrame):
    """
    Combine all project summaries and rank insights across projects.
    Following Git ranking approach for separate anomaly and risk ranking.

    Args:
        all_summaries (list): List of all project summary results
        output_dir (Path): Path to save output files
        jira_data_df: (DataFrame): DataFrame containing JIRA data

    Returns:
        dict: Combined and ranked results
    """
    logging.info(f"Combining and ranking insights from {len(all_summaries)} projects")

    # Collect all anomaly and risk insights
    all_anomaly_insights = []
    all_risk_insights = []

    for summary in all_summaries:
        project = summary.get("project", "UNKNOWN")

        # Process anomaly insights
        if "anomaly_insights" in summary:
            for insight in summary["anomaly_insights"]:
                # Ensure project is set
                if "project" not in insight:
                    insight["project"] = project

                if not insight.get("source"):
                    logging.warning("Anomaly insight has no source", extra=insight)
                    continue

                all_anomaly_insights.append(insight)

        # Process risk insights
        if "risk_insights" in summary:
            for insight in summary["risk_insights"]:
                # Ensure project is set
                if "project" not in insight:
                    insight["project"] = project

                if not insight.get("source"):
                    logging.warning("Risk insight has no source", extra=insight)
                    continue

                all_risk_insights.append(insight)

    # Rank all insights across projects - now uses the improved ranking method
    ranked_anomaly_insights = rank_jira_insights(all_anomaly_insights)
    ranked_risk_insights = rank_jira_insights(all_risk_insights)

    # Create combined result
    combined_result = {
        "anomaly_insights": ranked_anomaly_insights,
        "risk_insights": ranked_risk_insights,
    }

    # POST-PROCESS: Add correct ticket categories to the combined result
    logging.info("Post-processing ticket categories for combined insights")
    combined_result = add_ticket_categories_post_process(combined_result, jira_data_df)

    # Save the combined ranked results
    combined_path = output_dir / "combined_jira_anomaly_driven_insights.json"
    with open(combined_path, "w") as f:
        json.dump(combined_result, f, indent=2)

    logging.info(f"Saved combined ranked insights to {combined_path}")

    return combined_result


@instrumented
async def find_skip_a_meeting_insights_from_combined_insights(combined_insights, output_dir) -> SkipMeetingInsights:
    """
    Process the combined anomaly insights to generate skip-a-meeting insights.
    Uses 2 batch calls - one for all anomaly insights and one for all risk insights.
    Preserves the structure of combined_jira_anomaly_driven_insights but adds skip-a-meeting fields.
    Ensures only project_name field is kept, not the project field.

    Args:
        combined_insights (dict): Combined anomaly and risk insights from all projects
        output_dir (Path): Directory to save output files

    Returns:
        dict: Skip-a-meeting results in the same structure as combined insights
    """
    logging.info("Processing skip-a-meeting analysis for combined insights")

    # Create a new structure to hold our enhanced insights
    enhanced_results = {"anomaly_insights": [], "risk_insights": []}

    # Process all anomaly insights in one batch
    anomaly_insights = combined_insights.get("anomaly_insights", [])
    if anomaly_insights:
        logging.info(f"Processing {len(anomaly_insights)} anomaly insights in batch")

        # Prepare batch inputs for anomaly insights
        anomaly_inputs = []
        for insight in anomaly_insights:
            project_value = insight.get("project", "UNKNOWN")
            anomaly_inputs.append(
                {
                    "jira_anomaly": json.dumps(
                        {
                            "project": project_value,
                            "anomaly_insights": [insight],
                            "risk_insights": [],
                        }
                    )
                }
            )

        try:
            # Process all anomaly insights in one batch call
            results = await skip_meeting_analysis_chain.abatch(anomaly_inputs)

            for idx, (insight, result) in enumerate(zip(anomaly_insights, results)):
                project_value = insight.get("project", "UNKNOWN")

                # If the result has anomaly insights, add the first one (should be our enhanced insight)
                if result and "anomaly_insights" in result and len(result["anomaly_insights"]) > 0:
                    # Get the enhanced insight
                    skip_meeting_insight = result["anomaly_insights"][0]

                    # Make sure we have all original fields except 'project'
                    for key, value in insight.items():
                        if key != "project" and key not in skip_meeting_insight:
                            skip_meeting_insight[key] = value

                    # Ensure we have project_name but not project
                    if "project_name" not in skip_meeting_insight:
                        skip_meeting_insight["project_name"] = project_value

                    # Remove the project field if it exists
                    if "project" in skip_meeting_insight:
                        del skip_meeting_insight["project"]

                    # Add to our results
                    enhanced_results["anomaly_insights"].append(skip_meeting_insight)
                else:
                    # If no result, just add the original insight to maintain completeness
                    logging.warning(f"No skip-a-meeting insights generated for anomaly {idx + 1}, using original")

                    # Create a modified version of the original insight
                    modified_insight = insight.copy()

                    # Ensure we have project_name
                    if "project_name" not in modified_insight:
                        modified_insight["project_name"] = project_value

                    # Remove the project field
                    if "project" in modified_insight:
                        del modified_insight["project"]

                    enhanced_results["anomaly_insights"].append(modified_insight)

        except Exception:
            logging.exception("Pipeline Jira anomalies - Error processing anomaly insights batch")

            # Add modified versions of all original insights
            for idx, insight in enumerate(anomaly_insights):
                project_value = insight.get("project", "UNKNOWN")
                modified_insight = insight.copy()

                # Ensure we have project_name
                if "project_name" not in modified_insight:
                    modified_insight["project_name"] = project_value

                # Remove the project field
                if "project" in modified_insight:
                    del modified_insight["project"]

                enhanced_results["anomaly_insights"].append(modified_insight)

    # Process all risk insights in one batch
    risk_insights = combined_insights.get("risk_insights", [])
    if risk_insights:
        logging.info(f"Processing {len(risk_insights)} risk insights in batch")

        # Prepare batch inputs for risk insights
        risk_inputs = []
        for insight in risk_insights:
            project_value = insight.get("project", "UNKNOWN")
            risk_inputs.append(
                {
                    "jira_anomaly": json.dumps(
                        {
                            "project": project_value,
                            "anomaly_insights": [],
                            "risk_insights": [insight],
                        }
                    )
                }
            )

        try:
            # Process all risk insights in one batch call
            results = await skip_meeting_analysis_chain.abatch(risk_inputs)

            for idx, (insight, result) in enumerate(zip(risk_insights, results)):
                project_value = insight.get("project", "UNKNOWN")

                # If the result has risk insights, add the first one (should be our enhanced insight)
                if result and "risk_insights" in result and len(result["risk_insights"]) > 0:
                    # Get the enhanced insight
                    skip_meeting_insight = result["risk_insights"][0]

                    # Make sure we have all original fields except 'project'
                    for key, value in insight.items():
                        if key != "project" and key not in skip_meeting_insight:
                            skip_meeting_insight[key] = value

                    # Ensure we have project_name but not project
                    if "project_name" not in skip_meeting_insight:
                        skip_meeting_insight["project_name"] = project_value

                    # Remove the project field if it exists
                    if "project" in skip_meeting_insight:
                        del skip_meeting_insight["project"]

                    # Add to our results
                    enhanced_results["risk_insights"].append(skip_meeting_insight)
                else:
                    # If no result, just add the original insight to maintain completeness
                    logging.warning(f"No skip-a-meeting insights generated for risk {idx + 1}, using original")

                    # Create a modified version of the original insight
                    modified_insight = insight.copy()

                    # Ensure we have project_name
                    if "project_name" not in modified_insight:
                        modified_insight["project_name"] = project_value

                    # Remove the project field
                    if "project" in modified_insight:
                        del modified_insight["project"]

                    enhanced_results["risk_insights"].append(modified_insight)

        except Exception:
            logging.exception("Pipeline Jira anomalies - Error processing risk insights batch")

            # Add modified versions of all original insights
            for idx, insight in enumerate(risk_insights):
                project_value = insight.get("project", "UNKNOWN")
                modified_insight = insight.copy()

                # Ensure we have project_name
                if "project_name" not in modified_insight:
                    modified_insight["project_name"] = project_value

                # Remove the project field
                if "project" in modified_insight:
                    del modified_insight["project"]

                enhanced_results["risk_insights"].append(modified_insight)

    # Save the final results
    combined_skip_path = output_dir / "jira_all_projects_skip_meeting.json"
    with open(combined_skip_path, "w") as f:
        json.dump(enhanced_results, f, indent=2)
    logging.info(f"Saved combined skip-a-meeting results to {combined_skip_path}")

    return SkipMeetingInsights(**enhanced_results)


def run_jira_anomaly_driven_insights_pipeline(
    output_path: str,
    jira_data_df: pd.DataFrame,
) -> JiraCombinedInsights | None:
    logging.info(f"Running pipeline Jira anomalies with params: {output_path=}")

    with calls_context("jira_anomaly_driven_insights.json"):
        # Parse command line arguments

        # Create output directory if it doesn't exist
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load the CSV file
        try:
            df_old = jira_data_df.copy()
            df = df_old[REQUIRED_COLUMNS]
        except Exception as e:
            logging.exception(f"Pipeline Jira anomalies - Error loading CSV file")
            return None

        # Check if DataFrame is empty and validate required columns
        is_valid, missing_columns = validate_dataframe(df)
        if not is_valid:
            if "DataFrame is empty" in missing_columns:
                logging.error("Pipeline Jira anomalies - No JIRA data found. The CSV file is empty. Exiting.")
            else:
                logging.error(
                    f"Pipeline Jira anomalies - Missing required columns",
                    extra={"missing_columns": ", ".join(missing_columns)},
                )
            return None

        # Extract project names from issue keys
        df["project_name"] = df["issue_key"].apply(extract_project_from_issue_key)

        # Group by project name
        project_groups = df.groupby("project_name")
        all_results = []
        project_summary_results = []

        # Process each project group separately for anomaly insights
        projects_to_run = []
        for project_name, project_df in project_groups:
            if project_name == "UNKNOWN":
                logging.warning(f"Skipping 'UNKNOWN' project group with {len(project_df)} records")
                continue
            projects_to_run.append((project_name, project_df))

        tasks = [
            process_anomaly_driven_insights_for_project(
                jira_data_df, output_dir, all_results, project_summary_results, project_name, project_df
            )
            for project_name, project_df in projects_to_run
        ]

        asyncio.run(execute_concurrently(tasks))

        # Save anomaly summary results and create combined rankings
        if project_summary_results:
            # Save all projects summary first
            combined_summary_path = output_dir / "all_projects_summary.json"
            with open(combined_summary_path, "w") as f:
                json.dump(project_summary_results, f, indent=2)
            logging.info(f"Saved all projects summary to {combined_summary_path}")

            # Create combined and ranked insights across all projects
            combined_anomaly_results = combine_all_project_summaries_and_rank_insights(
                project_summary_results,
                output_dir,
                jira_data_df=jira_data_df,
            )
            # Process skip-a-meeting insights using combined anomaly results
            logging.info("Processing skip-a-meeting insights for combined results")
            skip_meeting_results = asyncio.run(
                find_skip_a_meeting_insights_from_combined_insights(combined_anomaly_results, output_dir)
            )

            try:
                anomaly_insights = []
                risk_insights = []
                for anomaly in combined_anomaly_results["anomaly_insights"]:
                    # remove "confidence" keyword to unify interface
                    anomaly["confidence_level"] = anomaly["confidence_level"].split(" ")[0]
                    anomaly_insights.append(JiraInsight(**anomaly))

                risk_insights = []
                for risk in combined_anomaly_results["risk_insights"]:
                    # remove "confidence" keyword to unify interface
                    risk["confidence_level"] = risk["confidence_level"].split(" ")[0]
                    risk_insights.append(JiraInsight(**risk))

                return JiraCombinedInsights(
                    anomaly_insights=anomaly_insights,
                    risk_insights=risk_insights,
                    skip_meeting_insights=skip_meeting_results,
                )
            except ValidationError:
                logging.exception("Pipeline Jira anomalies - Error creating pipeline result")
                return None
        return None


async def process_anomaly_driven_insights_for_project(
    jira_data_df: pd.DataFrame,
    output_dir: Path,
    all_results: list,
    project_summary_results: list,
    project_name: str,
    project_df: pd.DataFrame,
):
    project_results = await find_jira_insights_in_project(project_name, project_df, output_dir)

    # Add to all results for combined output
    all_results.extend(project_results)

    # Summarize project results if we have any
    if project_results:
        summarized_result = await summarize_insights_for_project(
            project_results,
            project_name,
            output_dir,
            jira_data_df=jira_data_df,
        )
        if summarized_result:
            project_summary_results.append(summarized_result)

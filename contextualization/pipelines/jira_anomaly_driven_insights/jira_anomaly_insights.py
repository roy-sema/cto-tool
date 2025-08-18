import asyncio
import json
import logging
from pathlib import Path

import pandas as pd
from otel_extensions import instrumented

from contextualization.conf.config import conf, llm_name
from contextualization.models.anomaly_insights import JiraCombinedInsights, JiraInsight
from contextualization.pipelines.anomaly_driven_insights.main import execute_concurrently
from contextualization.pipelines.common.anomalies_postprocessing import postprocess_anomaly_insights
from contextualization.pipelines.insights_aggregation_pipeline.schemas import SkipMeetingInsights
from contextualization.pipelines.jira_anomaly_driven_insights.batching_issues import (
    get_jira_issues_batches,
)
from contextualization.pipelines.jira_anomaly_driven_insights.prompts.jira_anomaly_prompt import (
    jira_anomaly_analysis_chain,
    jira_anomaly_analysis_summary_chain,
    llm_postprocessing_chain,
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


def validate_dataframe(df: pd.DataFrame) -> tuple[bool, list[str]]:
    if df.empty:
        return False, ["DataFrame is empty"]

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    is_valid = len(missing_columns) == 0

    return is_valid, missing_columns


def extract_project_from_issue_key(issue_key: str | None) -> str:
    """
    Extract project name from issue key (e.g., 'CON-110' -> 'CON')
    """
    if pd.isna(issue_key) or not isinstance(issue_key, str):
        return "UNKNOWN"
    parts = issue_key.split("-")
    if len(parts) > 0:
        return parts[0]
    return "UNKNOWN"


def add_ticket_categories_post_process(insights_json: dict, jira_data_df: pd.DataFrame) -> dict:
    """
    Post-process insights to add correct ticket categories by looking up CSV data.

    Args:
        insights_json (dict): The insights JSON with anomaly_insights
        jira_data_df: (DataFrame): Dataframe with ticket data

    Returns:
        dict: Updated insights JSON with correct ticket_categories
    """
    logger.info("Starting ticket category post-processing")

    df = jira_data_df

    total_insights_processed = 0
    total_categories_added = 0

    for insight_type, insight_list in insights_json.items():
        for idx, insight in enumerate(insight_list):
            try:
                ticket_ids = insight["source"]

                logger.debug(f"Processing {insight_type}[{idx}]: Found ticket IDs: {ticket_ids}")

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

                insight["ticket_categories"] = sorted(list(categories))

                total_insights_processed += 1
                total_categories_added += len(categories)

                logger.debug(f"  Final categories: {insight['ticket_categories']}")

            except Exception as e:
                logger.exception(
                    "Error processing insight",
                    extra={"insight_type": insight_type, "index": idx},
                )
                if "ticket_categories" not in insight:
                    insight["ticket_categories"] = []

    logger.info(
        f"Post-processing complete: {total_insights_processed} insights processed, {total_categories_added} total categories added"
    )
    return insights_json


@instrumented
async def find_insights_and_risks_in_jira_tickets(combined_text_batches: list[str]) -> list[dict]:
    input_list = [{"jira_data": chunk} for chunk in combined_text_batches]
    results = await jira_anomaly_analysis_chain.abatch(input_list)
    await asyncio.gather(
        *[postprocess_anomaly_insights(project_result, llm_postprocessing_chain) for project_result in results]
    )

    return results


def rank_jira_insights(insights_list: list[dict]) -> list[dict]:
    return list(sorted(insights_list, key=lambda insight: int(insight["significance_score"]), reverse=True))


@instrumented
async def summarize_insights_for_project(
    project_results: list[dict], project_name: str, output_dir: Path, jira_data_df: pd.DataFrame
) -> dict:
    logging.info(f"Summarizing insights for project: {project_name} across {len(project_results)} batches")
    output_summary_path = output_dir / f"{project_name}_summary_jira_anomalies.json"

    logging.info(f"Analyzing and summarizing {project_name} data...")
    summarized_result = await jira_anomaly_analysis_summary_chain.ainvoke({"jira_data": json.dumps(project_results)})

    logging.info(f"Post-processing ticket categories for {project_name}")
    summarized_result = add_ticket_categories_post_process(summarized_result, jira_data_df)

    for insight in summarized_result["anomaly_insights"]:
        insight["project"] = project_name

    summarized_result["anomaly_insights"] = rank_jira_insights(summarized_result["anomaly_insights"])
    summarized_result["anomaly_insights"] = [
        insight for insight in summarized_result["anomaly_insights"] if insight.get("source")
    ]

    # Add project metadata
    summarized_result["project"] = project_name
    summarized_result["batch_count"] = len(project_results)

    logging.info(f"Created summary with {len(summarized_result.get('anomaly_insights', []))} anomaly insights")
    with open(output_summary_path, "w") as f:
        json.dump(summarized_result, f, indent=2)

    logging.info(f"Saved summarized results to {output_summary_path}")

    return summarized_result


@instrumented
async def find_jira_insights_in_project(project_name: str, project_df: pd.DataFrame, output_dir: Path) -> list[dict]:
    logging.info(f"Processing project: {project_name} with {len(project_df)} records")

    # Define output paths for this project
    base_filename = f"{project_name}_anomaly_analysis"
    output_json_path = output_dir / f"{project_name}_anomaly_insight.json"
    error_log_path = output_dir / f"{base_filename}_error.csv"

    project_results = await find_insights_and_risks_in_jira_tickets(await get_jira_issues_batches(project_df))
    project_results = [
        ({**result, "project": project_name} if isinstance(result, dict) else result) for result in project_results
    ]

    with open(output_json_path, "w") as f:
        json.dump(project_results, f, indent=2)

    logging.info(f"Analysis completed for project {project_name} with {len(project_results)} batch results")
    return project_results


def combine_all_project_summaries_and_rank_insights(
    all_summaries: list[dict], output_dir: Path, jira_data_df: pd.DataFrame
) -> dict:
    logging.info(f"Combining and ranking insights from {len(all_summaries)} projects")

    all_anomaly_insights = []

    for summary in all_summaries:
        all_anomaly_insights.extend(summary["anomaly_insights"])

    combined_result = {
        "anomaly_insights": rank_jira_insights(all_anomaly_insights),
    }

    combined_path = output_dir / "combined_jira_anomaly_driven_insights.json"
    with open(combined_path, "w") as f:
        json.dump(combined_result, f, indent=2)

    logging.info(f"Saved combined ranked insights to {combined_path}")

    return combined_result


async def enhance_insight_with_skip_a_meeting(insight: dict) -> dict:
    project = insight.get("project", "UNKNOWN")
    chain_input = {
        "jira_anomaly": json.dumps(
            {
                "project": project,
                "insight": insight,
            }
        )
    }
    result = await skip_meeting_analysis_chain.ainvoke(chain_input)
    # some schemas use project_name, some use project - keeping backward compatibility
    insight["project_name"] = project
    if result["skip_a_meeting_insight"] is not None:
        insight.update(result["skip_a_meeting_insight"])

    return insight


@instrumented
async def find_skip_a_meeting_insights_from_combined_insights(
    combined_insights: dict, output_dir: Path
) -> SkipMeetingInsights:
    logging.info("Processing skip-a-meeting analysis for combined insights")

    anomaly_insights = combined_insights.get("anomaly_insights", [])
    tasks = [enhance_insight_with_skip_a_meeting(insight) for insight in anomaly_insights]

    await asyncio.gather(*tasks)

    enhanced_results = {"anomaly_insights": anomaly_insights}

    combined_skip_path = output_dir / "jira_all_projects_skip_meeting.json"
    with open(combined_skip_path, "w") as f:
        json.dump(enhanced_results, f, indent=2)
    logging.info(f"Saved combined skip-a-meeting results to {combined_skip_path}")

    return SkipMeetingInsights(**enhanced_results)


async def run_jira_anomaly_driven_insights_pipeline(
    output_path: str,
    jira_data_df: pd.DataFrame,
) -> JiraCombinedInsights | None:
    logging.info(f"Running pipeline Jira anomalies with params: {output_path=}")

    with calls_context("jira_anomaly_driven_insights.yaml"):
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        df_old = jira_data_df.copy()
        df = df_old[REQUIRED_COLUMNS]

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

        df["project_name"] = df["issue_key"].apply(extract_project_from_issue_key)

        project_groups = df.groupby("project_name")

        projects_to_run = []
        for project_name, project_df in project_groups:
            if project_name == "UNKNOWN":
                logging.warning(f"Skipping 'UNKNOWN' project group with {len(project_df)} records")
                continue
            projects_to_run.append((project_name, project_df))

        tasks = [
            process_anomaly_driven_insights_for_project(jira_data_df, output_dir, project_name, project_df)
            for project_name, project_df in projects_to_run
        ]

        results = await execute_concurrently(tasks)
        project_summary_results = [r for r in results if r is not None]

        if project_summary_results:
            combined_summary_path = output_dir / "all_projects_summary.json"
            with open(combined_summary_path, "w") as f:
                json.dump(project_summary_results, f, indent=2)
            logging.info(f"Saved all projects summary to {combined_summary_path}")

            combined_anomaly_results = combine_all_project_summaries_and_rank_insights(
                project_summary_results,
                output_dir,
                jira_data_df=jira_data_df,
            )
            logging.info("Processing skip-a-meeting insights for combined results")
            skip_meeting_results = await find_skip_a_meeting_insights_from_combined_insights(
                combined_anomaly_results, output_dir
            )

            return JiraCombinedInsights(
                anomaly_insights=[JiraInsight(**insight) for insight in combined_anomaly_results["anomaly_insights"]],
                skip_meeting_insights=skip_meeting_results,
            )

        return None


async def process_anomaly_driven_insights_for_project(
    jira_data_df: pd.DataFrame,
    output_dir: Path,
    project_name: str,
    project_df: pd.DataFrame,
) -> dict | None:
    project_results = await find_jira_insights_in_project(project_name, project_df, output_dir)

    if project_results:
        return await summarize_insights_for_project(
            project_results,
            project_name,
            output_dir,
            jira_data_df=jira_data_df,
        )

    return None

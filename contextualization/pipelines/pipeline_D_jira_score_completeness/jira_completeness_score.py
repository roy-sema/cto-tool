import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from otel_extensions import instrumented

from contextualization.conf.config import conf, llm_name
from contextualization.models.ticket_completeness import StageCategory, TicketCategory
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.main import (
    process_jira_data,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.jira_completeness_score_prompt import (
    jira_completeness_score_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.jira_completeness_score_summary import (
    category_summary_chain,
    final_summary_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.jira_ticket_categorization_prompt import (
    categorize_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.stage_category_prompt import (
    stage_classification_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.work_group_summary_prompt import (
    work_group_summary_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.work_groups_overall_summary_prompt import (
    grouped_work_groups_summary_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.schemas import (
    PipelineDResult,
    QualitySummary,
    TicketCompletenessScoreResult,
    categorize_quality,
)
from contextualization.utils.vcr_mocks import calls_context

logger = logging.getLogger(__name__)


token_limit = conf["llms"][llm_name]["token_limit"]
batch_threshold = conf["llms"][llm_name]["batch_threshold"]


@instrumented
async def assign_jira_completeness_score(df: pd.DataFrame) -> pd.DataFrame:
    async def assign_jira_completeness_score_with_token_callback(jira_tickets_list):
        return await jira_completeness_score_chain.abatch(
            [{"jira_ticket_row": jira_ticket} for jira_ticket in jira_tickets_list]
        )

    selected_columns = [
        "issue_key",
        "summary",
        "Issue Type",
        "components",
        "description",
        "priority",
        "labels",
        "attachment",
        "issuelinks",
        "assignee",
        "status",
    ]
    column_names = " | ".join(selected_columns)

    jira_tickets_list = (
        df[selected_columns]
        .apply(
            lambda x: column_names + "\n" + " | ".join(map(str, x)).replace("\n", " "),
            axis=1,
        )
        .tolist()
    )

    logger.info("Processing Jira completeness score", extra={"jira_ticket_count": len(jira_tickets_list)})
    results = await assign_jira_completeness_score_with_token_callback(jira_tickets_list)
    success_df = pd.DataFrame(results, index=df.index[: len(results)])
    return df.merge(success_df, left_index=True, right_index=True)


def add_quality_category(jira_file_path: Path, jira_data: pd.DataFrame) -> pd.DataFrame:
    """
    Reads a CSV file, categorizes each row's score, and adds a 'quality_category' column.

    Args:
        jira_file_path (str): Path to the input CSV file.
        jira_data: (DataFrame): DataFrame with JIRA data.
    Returns:
        pd.DataFrame: Updated DataFrame with 'quality_category' column.
    """

    # Ensure 'jira_completeness_score' exists
    if "jira_completeness_score" not in jira_data.columns:
        raise ValueError("Can not add quality_category: Missing 'jira_completeness_score' column in CSV")

    # Convert scores to numeric
    jira_data["jira_completeness_score"] = pd.to_numeric(jira_data["jira_completeness_score"], errors="coerce")

    # Drop rows with invalid scores (NaN after coercion)
    jira_data = jira_data.dropna(subset=["jira_completeness_score"])

    # Check if data is empty after dropping NaN
    if jira_data.empty:
        error_msg = "No JIRA ticket data found for quality_category(empty DataFrame)"
        logging.error(error_msg)
        raise ValueError(error_msg)

    # Add quality category
    jira_data["quality_category"] = jira_data["jira_completeness_score"].apply(categorize_quality)

    # Save the file
    jira_data.to_csv(jira_file_path, index=False)

    return jira_data


# Generates the Ticket Completeness Score summary report
@instrumented
async def generate_jira_quality_summary(jira_tickets_data: pd.DataFrame, summary_output_path: Path) -> dict[str, Any]:
    """Generate a quality summary report from JIRA completeness scores, categorizing tickets by stage, by catgory, by quality_category.

    Args:
        jira_tickets_data (pd.DataFrame): DataFrame containing JIRA completeness scores
        summary_output_path (str): Path to save the quality summary report JSON output

    Returns:
        dict: The quality summary results
    """
    required_columns = [
        "issue_key",
        "jira_completeness_score",
        "explanation_jira_completeness_score",
        "stage_category",
        "llm_category",
    ]

    missing_columns = [col for col in required_columns if col not in jira_tickets_data.columns]
    if missing_columns:
        error_msg = f"Required columns missing from data: {missing_columns}"
        logging.error(error_msg)
        raise ValueError(error_msg)

    jira_tickets_data["jira_completeness_score"] = pd.to_numeric(
        jira_tickets_data["jira_completeness_score"], errors="coerce"
    )
    jira_tickets_data = jira_tickets_data.dropna(subset=["jira_completeness_score"])

    # Check if data is empty after dropping NaN
    if jira_tickets_data.empty:
        error_msg = "No JIRA ticket data found for quality summary (empty DataFrame)"
        logging.error(error_msg)
        raise ValueError(error_msg)

    jira_tickets_data["project_name"] = jira_tickets_data["issue_key"].apply(lambda x: x.split("-")[0])
    if "quality_category" not in jira_tickets_data.columns:
        jira_tickets_data["quality_category"] = jira_tickets_data["jira_completeness_score"].apply(categorize_quality)

    def summarize_by_field(df, field):
        # Determine the output key name
        key_name = "stage" if field == "stage_category" else "category"

        # Group and aggregate once
        summary_df = (
            df.groupby(field)
            .agg(
                ticket_count=("jira_completeness_score", "count"),
                average_count=("jira_completeness_score", "mean"),
            )
            .reset_index()
        )

        # Apply quality categorization in a vectorized way
        summary_df["average_count"] = summary_df["average_count"].round(2)
        summary_df["quality_category"] = summary_df["average_count"].apply(categorize_quality)
        summary_df = summary_df.rename(columns={field: key_name})

        # Convert to sorted list of dictionaries
        return summary_df.sort_values(by=key_name).to_dict(orient="records")

    overall = {
        "total_projects": jira_tickets_data["project_name"].nunique(),
        "project_names": sorted(jira_tickets_data["project_name"].unique().tolist()),
        "average_score": round(jira_tickets_data["jira_completeness_score"].mean(), 2),
        "by_stage": summarize_by_field(jira_tickets_data, "stage_category"),
        "by_category": summarize_by_field(jira_tickets_data, "llm_category"),
    }

    final_summary_inputs = []
    for project, df in jira_tickets_data.groupby("project_name"):
        avg_score = round(df["jira_completeness_score"].mean(), 2)
        top_3 = df.nlargest(3, "jira_completeness_score")[
            [
                "issue_key",
                "jira_completeness_score",
                "stage_category",
                "llm_category",
                "quality_category",
                "explanation_jira_completeness_score",
            ]
        ].to_dict(orient="records")
        bottom_3 = df.nsmallest(3, "jira_completeness_score")[
            [
                "issue_key",
                "jira_completeness_score",
                "stage_category",
                "llm_category",
                "quality_category",
                "explanation_jira_completeness_score",
            ]
        ].to_dict(orient="records")
        sample_tickets = {"top_3": top_3, "bottom_3": bottom_3}

        by_stage = summarize_by_field(df, "stage_category")
        by_category = summarize_by_field(df, "llm_category")

        final_summary_inputs.append(
            {
                "project": project,
                "sample_tickets": sample_tickets,
                "jira_tickets_data": {
                    "average_score": avg_score,
                    "by_stage": by_stage,
                    "by_category": by_category,
                },
            }
        )

    key_findings = await final_summary_chain.abatch(
        [{"jira_tickets_data": input_data["jira_tickets_data"]} for input_data in final_summary_inputs]
    )

    by_project = []
    for i, input_data in enumerate(final_summary_inputs):
        by_project.append(
            {
                "project": input_data["project"],
                "sample_tickets": input_data["sample_tickets"],
                "average_score": input_data["jira_tickets_data"]["average_score"],
                "by_stage": input_data["jira_tickets_data"]["by_stage"],
                "by_category": input_data["jira_tickets_data"]["by_category"],
                "key_findings": key_findings[i],
            }
        )

    complete_summary = {"all_projects": overall, "by_project": by_project}

    with open(summary_output_path, "w") as f:
        json.dump(complete_summary, f, indent=2)
    logging.info(f"Saved JIRA quality summary to {summary_output_path}")

    return complete_summary


@instrumented
async def generate_jira_quality_summary_legacy(df_quality: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Generate a quality summary from JIRA completeness scores, categorizing tickets
    into excellent, average, and initial quality based on their scores.
    """

    # Function to convert dataframe to the required format for LLM
    def format_df_for_llm(dataframe, format_columns):
        # Filter to ensure we only use columns that exist in the dataframe
        available_columns = [col for col in format_columns if col in dataframe.columns]

        # If no available columns, return an empty list
        if not available_columns:
            return []

        # Create a string with column names
        column_names = " | ".join(available_columns)

        # Convert each row to the required format
        formatted_data = (
            dataframe[available_columns]
            .apply(
                lambda x: column_names + "\n" + " | ".join(map(str, x)).replace("\n", " "),
                axis=1,
            )
            .tolist()
        )

        return formatted_data

    # Columns to include in the formatted data
    columns_to_format = [
        "issue_key",
        "jira_completeness_score",
        "evaluation_jira_completeness_score",
    ]

    # Define required columns
    required_columns = [
        "issue_key",
        "jira_completeness_score",
        "evaluation_jira_completeness_score",
    ]

    # Prepare data for all projects
    project_data = []
    all_category_inputs = []
    all_final_inputs = []
    category_input_mappings = []
    final_input_mappings = []

    for project_name, jira_tickets_data in df_quality.groupby("project_name"):
        if jira_tickets_data.empty:
            logging.error(
                "Pipeline Jira completeness score - No JIRA ticket data provided for quality summary (empty DataFrame)"
            )
            continue

        df = jira_tickets_data

        logging.info(f"Preparing quality summary for project {project_name} with {len(df)} ticket records")
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logging.error(
                f"Pipeline Jira completeness score - Required columns missing from data",
                extra={"missing_columns": missing_columns},
            )
            continue

        # Convert score to numeric if it's not already
        df["jira_completeness_score"] = pd.to_numeric(df["jira_completeness_score"], errors="coerce")

        # Drop rows with NaN scores if any
        if df["jira_completeness_score"].isna().any():
            logging.warning(f"Dropping {df['jira_completeness_score'].isna().sum()} rows with missing scores")
            df = df.dropna(subset=["jira_completeness_score"])

            if df.empty:
                logging.error("Pipeline Jira completeness score - All rows had missing scores, no data to analyze")
                continue

        # Calculate average score
        average_score = round(df["jira_completeness_score"].mean(), 2)

        # Create three different dataframes based on score ranges
        initial_quality_df = df[df["jira_completeness_score"] < 30].copy()
        average_df = df[(df["jira_completeness_score"] >= 30) & (df["jira_completeness_score"] < 70)].copy()
        excellent_df = df[df["jira_completeness_score"] >= 70].copy()

        logging.info(
            f"Project {project_name} - Excellent: {len(excellent_df)}, Average: {len(average_df)}, Initial: {len(initial_quality_df)}"
        )

        # Prepare project data structure
        project_info = {
            "project_name": project_name,
            "df": df,
            "average_score": average_score,
            "excellent_df": excellent_df,
            "average_df": average_df,
            "initial_quality_df": initial_quality_df,
            "summaries": {},
            "category_batch_indices": [],
        }

        # Prepare category batch inputs for this project
        # Generate summary for excellent tickets
        if not excellent_df.empty:
            excellent_formatted = format_df_for_llm(excellent_df, columns_to_format)
            all_category_inputs.append({"jira_tickets_data": excellent_formatted})
            category_input_mappings.append((len(project_data), "excellent"))
            project_info["category_batch_indices"].append(len(all_category_inputs) - 1)
        else:
            project_info["summaries"]["excellent"] = {
                "patterns": "No tickets with scores 70 or above were found in the dataset.",
                "examples": [],
                "recommendations": [],
            }

        # Generate summary for average tickets
        if not average_df.empty:
            average_formatted = format_df_for_llm(average_df, columns_to_format)
            all_category_inputs.append({"jira_tickets_data": average_formatted})
            category_input_mappings.append((len(project_data), "average"))
            project_info["category_batch_indices"].append(len(all_category_inputs) - 1)
        else:
            project_info["summaries"]["average"] = {
                "patterns": "No tickets with scores between 30 and 70 were found in the dataset.",
                "examples": [],
                "recommendations": [],
            }

        # Generate summary for initial quality tickets
        if not initial_quality_df.empty:
            initial_quality_formatted = format_df_for_llm(initial_quality_df, columns_to_format)
            all_category_inputs.append({"jira_tickets_data": initial_quality_formatted})
            category_input_mappings.append((len(project_data), "initial_quality"))
            project_info["category_batch_indices"].append(len(all_category_inputs) - 1)
        else:
            project_info["summaries"]["initial_quality"] = {
                "patterns": "No tickets with scores below 30 were found in the dataset.",
                "examples": [],
                "recommendations": [],
            }

        project_data.append(project_info)

    # Process all category summaries in a single batch
    if all_category_inputs:
        logging.info(f"Processing {len(all_category_inputs)} category summaries across all projects in batch...")
        category_results = await category_summary_chain.abatch(all_category_inputs)

        # Map category results back to projects
        for i, (project_idx, category_type) in enumerate(category_input_mappings):
            project_data[project_idx]["summaries"][category_type] = category_results[i]

    # Prepare final summary inputs for all projects
    for project_info in project_data:
        final_summary_input = {
            "total_tickets": len(project_info["df"]),
            "average_score": project_info["average_score"],
            "excellent_tickets": {
                "count": len(project_info["excellent_df"]),
                "tickets": (
                    project_info["excellent_df"]["issue_key"].tolist() if not project_info["excellent_df"].empty else []
                ),
                "summary": project_info["summaries"]["excellent"],
            },
            "average_tickets": {
                "count": len(project_info["average_df"]),
                "tickets": (
                    project_info["average_df"]["issue_key"].tolist() if not project_info["average_df"].empty else []
                ),
                "summary": project_info["summaries"]["average"],
            },
            "initial_quality_tickets": {
                "count": len(project_info["initial_quality_df"]),
                "tickets": project_info["initial_quality_df"]["issue_key"].tolist()
                if not project_info["initial_quality_df"].empty
                else [],
                "summary": project_info["summaries"]["initial_quality"],
            },
        }
        all_final_inputs.append({"jira_tickets_data": final_summary_input})
        final_input_mappings.append(len(all_final_inputs) - 1)

    if not all_final_inputs:
        return []

    # Process all final summaries in a single batch
    final_results = []
    logging.info(f"Processing {len(all_final_inputs)} final summaries across all projects in batch...")
    final_summaries = await final_summary_chain.abatch(all_final_inputs)

    # Build final results
    for i, project_info in enumerate(project_data):
        final_summary = final_summaries[i] if i < len(final_summaries) else None

        final_results.append(
            {
                "total_tickets": len(project_info["df"]),
                "project_name": project_info["project_name"],
                "average_score": project_info["average_score"],
                "excellent_tickets": {
                    "count": len(project_info["excellent_df"]),
                    "summary": project_info["summaries"]["excellent"],
                },
                "average_tickets": {
                    "count": len(project_info["average_df"]),
                    "summary": project_info["summaries"]["average"],
                },
                "initial_quality_tickets": {
                    "count": len(project_info["initial_quality_df"]),
                    "summary": project_info["summaries"]["initial_quality"],
                },
                "final_summary": final_summary,
            }
        )

    return final_results


@instrumented
async def categorise_ticket(batch_df: pd.DataFrame) -> list[str]:
    """
    Categorize all tickets in a batch using .batch() method.

    Args:
        batch_df: DataFrame containing the batch of tickets to process

    Returns:
        List of categories corresponding to each row in the batch
    """
    # Prepare batch inputs - one input dict per ticket
    batch_inputs = []
    results = []

    for _, row in batch_df.iterrows():
        text = row["description"]
        if pd.isna(text) or not isinstance(text, str) or text.strip() == "":
            logging.warning(f"No description found for ticket {row['issue_key']}, defaulting to category OTHER")
            results.append(TicketCategory.OTHER.value)
            batch_inputs.append(None)  # Placeholder
        else:
            results.append(None)  # Will be filled by LLM
            batch_inputs.append({"jira_ticket_row": text})

    # Filter out None inputs for batch processing
    valid_inputs = [inp for inp in batch_inputs if inp is not None]
    valid_indices = [i for i, inp in enumerate(batch_inputs) if inp is not None]

    if not valid_inputs:
        return results  # All were empty

    batch_responses = await categorize_chain.abatch(valid_inputs)

    for i, response in enumerate(batch_responses):
        result_index = valid_indices[i]

        if isinstance(response, dict):
            category = response.get("llm_category")
            try:
                category = TicketCategory(category)
            except ValueError:
                logging.warning(f"Invalid {category=}, {response=} setting to OTHER")
                category = TicketCategory.OTHER

            results[result_index] = category.value

    return results


@instrumented
async def process_jira_tickets(df: pd.DataFrame, tiktoken_column: str = "description_tokens") -> pd.DataFrame:
    """
    Process all JIRA tickets in batches with 1 LLM call per batch.

    Args:
        df: DataFrame containing JIRA tickets with 'description' column
        tiktoken_column: Column name containing token counts for batching

    Returns:
        DataFrame with 'llm_category' column added
    """
    logger.info("Processing all tickets in batches")

    # Initialize results column
    df["llm_category"] = ""
    batches = [df]
    logger.info(f"Created {len(batches)} batches for processing")
    total_processed = 0

    # Process each batch
    for batch_num, batch_df in enumerate(batches, 1):
        logger.info(f"Processing batch {batch_num}/{len(batches)}")

        batch_categories = await categorise_ticket(batch_df)

        # Store results back in original dataframe
        for (original_idx, _), category in zip(batch_df.iterrows(), batch_categories):
            df.at[original_idx, "llm_category"] = category

        total_processed += len(batch_df)

        logger.info(f"Batch {batch_num}")

    logger.info("Ticket processing completed")

    return df


@instrumented
def analyze_jira_completeness_by_category(df: pd.DataFrame, output_path: str | Path) -> None:
    """
    Analyzes Jira data by LLM category and creates a JSON report file.

    Args:
        df (DataFrame): DataFrame containing Jira data
        output_path (str): Path where the JSON result will be saved (default: 'jira_analysis_result.json')
    """

    # Remove rows with null/missing llm_category or jira_completeness_score
    initial_count = len(df)
    df_clean = df.dropna(subset=["llm_category", "jira_completeness_score"])
    dropped_count = initial_count - len(df_clean)

    if df_clean.empty:
        logger.error(
            "No valid data found after cleaning - missing required columns",
            extra={
                "initial_rows": initial_count,
                "required_columns": ["llm_category", "jira_completeness_score"],
            },
        )
        return

    if dropped_count > 0:
        logger.warning(
            "Dropped rows with missing required data",
            extra={
                "dropped_rows": dropped_count,
                "remaining_rows": len(df_clean),
                "drop_percentage": round((dropped_count / initial_count) * 100, 1),
            },
        )

    # Initialize the result dictionary
    result = {
        "average_completeness_score_per_category": {},
        "top_tickets_by_category": {},
        "bottom_tickets_by_category": {},
    }

    # Get unique categories
    categories = df_clean["llm_category"].unique()
    logger.info(f"Starting analysis by category, : {len(categories)}, categories: {categories}")
    logger.info(f"Sotal tickets to analyze: {len(df_clean)}")

    category_stats = []
    for category in categories:
        # Filter data for current category
        category_data = df_clean[df_clean["llm_category"] == category]

        # Calculate average completeness score
        avg_score = round(category_data["jira_completeness_score"].mean(), 2)
        result["average_completeness_score_per_category"][category] = avg_score

        category_stats.append(
            {
                "category": category,
                "ticket_count": len(category_data),
                "average_score": avg_score,
            }
        )

        # Sort by completeness score for top and bottom tickets
        sorted_data = category_data.sort_values("jira_completeness_score", ascending=False)

        # Helper function to create ticket entry
        def create_ticket_entry(ticket):
            # Get full description
            full_description = ""
            if pd.notna(ticket["description"]) and ticket["description"]:
                full_description = str(ticket["description"])

            return {
                "issue_key": ticket["issue_key"],
                "summary": ticket["summary"],
                "score": float(ticket["jira_completeness_score"]),
                "priority": (ticket["priority"] if pd.notna(ticket["priority"]) else "Not Set"),
                "issue_type": (ticket["Issue Type"] if pd.notna(ticket["Issue Type"]) else "Unknown"),
                "status": (ticket["status"] if pd.notna(ticket["status"]) else "Unknown"),
                "description": full_description,
                "created": (ticket["created"] if pd.notna(ticket["created"]) else "Unknown"),
            }

        # Get top 3 highest-scoring tickets
        top_3 = []
        for _, ticket in sorted_data.head(3).iterrows():
            top_3.append(create_ticket_entry(ticket))

        result["top_tickets_by_category"][category] = top_3

        # Get bottom 3 lowest-scoring tickets (reverse the tail to get lowest first)
        bottom_3 = []
        for _, ticket in sorted_data.tail(3).iloc[::-1].iterrows():
            bottom_3.append(create_ticket_entry(ticket))

        result["bottom_tickets_by_category"][category] = bottom_3

    # Save to JSON file
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(
        f"Analysis completed successfully - results saved to {output_path}",
    )
    logger.info(f"Total categories analyzed: {len(categories)}")
    logger.info(f"Total tickets analyzed: {len(df_clean)}")
    logger.info(f"Category statistics: {category_stats}")

    return result


@instrumented
async def generate_jcs_grouped_by_work_group(df: pd.DataFrame, json_file_path: str) -> dict[str, Any]:
    # Validate necessary columns
    if "jira_completeness_score" not in df.columns:
        raise ValueError("CSV must contain a 'jira_completeness_score' column.")
    if "Categorization_of_initiative_git" not in df.columns:
        raise ValueError("CSV must contain a 'Categorization_of_initiative_git' column.")

    # Define the columns to extract for each ticket
    ticket_columns = [
        "issue_key",
        "summary",
        "jira_completeness_score",
        "priority",
        "Issue Type",
        "status",
        "description",
        "created",
    ]

    # Group by initiative
    grouped = df.groupby("Categorization_of_initiative_git")
    output = {}

    for initiative, group_df in grouped:
        # Sort group by score descending
        sorted_group = group_df.sort_values(by="jira_completeness_score", ascending=False)

        # Compute average score
        avg_score = round(group_df["jira_completeness_score"].mean(), 2)

        # Select top and bottom 3 tickets
        output[initiative] = {
            "average_score": avg_score,
            "top_tickets": sorted_group[ticket_columns].head(3).to_dict(orient="records"),
            "bottom_tickets": sorted_group[ticket_columns].tail(3).to_dict(orient="records"),
        }

        # Generate per-initiative summary using LLM
        summary = await work_group_summary_chain.ainvoke({"work_group_data": output[initiative]})
        output[initiative].update(summary)

    summary = await grouped_work_groups_summary_chain.ainvoke({"input_json": output})
    output.update(summary)

    # Write result to JSON file
    with open(json_file_path, "w") as json_file:
        json.dump(output, json_file, indent=2)
        logging.info(f"Output JSON grouped by initiative is stored successfully at {json_file_path}")

    return output


@instrumented
async def categorise_jira_ticket_stages(jira_data_with_score_df: pd.DataFrame, output_base_path: str) -> pd.DataFrame:
    """
    Categorizes Jira ticket stages using inferred categories from unique statuses.

    Parameters:
    - jira_data_with_score_df (DataFrame): DataFrame with Jira data.
    - output_base_path (str): Directory where the output CSV file will be saved.

    Returns:
    - DataFrame: DataFrame with Jira data.
    """

    # Removing Duplicates
    jira_data_with_score_df = jira_data_with_score_df.drop_duplicates(subset=["issue_key"], keep="last")

    # Initializing stage_category column
    jira_data_with_score_df["stage_category"] = ""

    # Extracting and normalizing unique statuses
    unique_statuses = set(jira_data_with_score_df["status"].dropna().str.strip().str.lower())

    logging.info("Inferring stage categories using language model.")
    category_mappings = await stage_classification_chain.ainvoke({"jira_ticket_stages": unique_statuses})
    # Creating final mapping from inference results
    final_mappings = {}
    for category_mapping in category_mappings["stage_categories"]:
        final_mappings[category_mapping["original_stage"]] = category_mapping["category"]

    # Normalizing status field for mapping
    jira_data_with_score_df["normalized_stage"] = (
        jira_data_with_score_df["status"]
        .fillna("")  # handle NaN
        .str.strip()
        .str.lower()
    )

    # Mapping normalized stages to category labels
    jira_data_with_score_df["stage_category"] = jira_data_with_score_df["normalized_stage"].map(final_mappings)

    # Dropping up temporary column
    jira_data_with_score_df.drop(columns=["normalized_stage"], inplace=True)

    custom_name = "jira_stage_classification.csv"
    full_output_path = os.path.join(output_base_path, custom_name)

    logging.info(f"Saving stage categorized Jira data to: {full_output_path}")
    jira_data_with_score_df.to_csv(full_output_path, index=False)

    return jira_data_with_score_df


# Aggregate the Ticket Completeness Score by stage
@instrumented
def aggregate_TCS_wrt_stage_category(df: pd.DataFrame, output_base_path: str) -> str:
    # Validate necessary columns
    if "jira_completeness_score" not in df.columns:
        raise ValueError("CSV must contain a 'jira_completeness_score' column.")
    if "stage_category" not in df.columns:
        raise ValueError("CSV must contain a 'Categorization_of_initiative_git' column.")

    required_columns = [
        "issue_key",
        "summary",
        "jira_completeness_score",
        "priority",
        "Issue Type",
        "stage_category",
        "description",
        "created",
    ]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    grouped = df.groupby("stage_category")
    avg_scores = grouped["jira_completeness_score"].mean().round(2).to_dict()

    top_tickets = {}
    bottom_tickets = {}

    for category, group_df in grouped:
        sorted_group = group_df.sort_values(by="jira_completeness_score", ascending=False)
        top_tickets[category] = sorted_group[required_columns].head(3).to_dict(orient="records")
        bottom_tickets[category] = sorted_group[required_columns].tail(3).to_dict(orient="records")

    output = {
        "average_completeness_score_per_category": avg_scores,
        "top_tickets_by_category": top_tickets,
        "bottom_tickets_by_category": bottom_tickets,
    }

    os.makedirs(output_base_path, exist_ok=True)
    output_file_path = os.path.join(output_base_path, "tcs_aggregated_wrt_stage_categories.json")

    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    logging.info(f"JCS aggregation successfully written to {output_file_path}")
    return output_file_path


async def run_jira_completeness_score_pipeline(
    output_path: str,
    jira_url: str | None = None,
    confluence_user: str | None = None,
    confluence_token: str | None = None,
    jira_access_token: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    jira_project_names: list[str] | None = None,
) -> PipelineDResult | None:
    logging.info(
        f"Running pipeline D with params: {jira_url=} {confluence_user=} confluence_token=<REDACTED> "
        f"jira_access_token=<REDACTED> {start_date=} {end_date=} {jira_project_names=} {output_path=}"
    )
    with calls_context("pipeline_d.yaml"):
        start_date = start_date.split("T")[0] if start_date else None
        end_date = end_date.split("T")[0] if end_date else None
        # Create output directory if it doesn't exist
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Define output paths
        output_path = output_dir / "jira_data_with_jira_completeness_score.csv"
        error_log_path = output_dir / "jira_data_with_score_error.csv"
        work_group_wise_data = output_dir / "work_group_wise_jcs_data.json"

        # Check if jira_project_names provided
        if not jira_project_names:
            logging.info("No JIRA project selected provided.")
            return None
        # Process the JIRA data
        df = await process_jira_data(
            jira_url=jira_url,
            project_names=jira_project_names,
            confluence_user=confluence_user,
            confluence_token=confluence_token,
            start_date=start_date,
            end_date=end_date,
            jira_access_token=jira_access_token,
        )

        if df.empty:
            logging.warning("Pipeline Jira completeness score - No JIRA data found. Exiting.")
            return None

        # Assign completeness scores
        df_output = await assign_jira_completeness_score(df)

        # Add stage category and generate TCS by stage
        staged_categorised_jira_df = await categorise_jira_ticket_stages(df_output, str(output_dir))
        staged_json_path = aggregate_TCS_wrt_stage_category(staged_categorised_jira_df, str(output_dir))

        df_stage = staged_categorised_jira_df

        # Add llm_category and generate TCS by LLM category
        jira_data_with_llm_category_path = output_dir / "jira_data_with_score.csv"

        # For TCS we need all of the tickets, no only To Do and In Progress
        df_llm_categorised = await process_jira_tickets(df_stage, tiktoken_column="description_tokens")
        ticket_completeness_scores = [
            TicketCompletenessScoreResult(
                **ticket,
                project_name=ticket["issue_key"].split("-")[0],
                quality_category=categorize_quality(ticket["jira_completeness_score"]),
            )
            for ticket in df_llm_categorised.replace({pd.NA: None, pd.NaT: None}).to_dict(orient="records")
        ]

        # NOTE: For further implementation ignore stages done, won't do and backlog
        IGNORED_STAGES = [
            StageCategory.DONE.value,
            StageCategory.WILL_NOT_DO.value,
            StageCategory.BACKLOG.value,
        ]
        df_stage_filtered = df_llm_categorised[~df_stage["stage_category"].isin(IGNORED_STAGES)]
        if df_stage_filtered.empty:
            logging.warning(
                "Pipeline D Jira completeness score - Can not generate further insights: NO data in 'To Do', 'In Progress' stages"
            )
            return PipelineDResult(
                ticket_completeness_scores=ticket_completeness_scores, jira_data_df=df_stage_filtered
            )

        df_stage_filtered.to_csv(jira_data_with_llm_category_path, index=False)

        llm_categorized_json = output_dir / "jira_category_breakdown.json"
        jira_completeness_by_category = analyze_jira_completeness_by_category(df_stage_filtered, llm_categorized_json)

        # Define output path for jira quality summary(old)
        summary_output_path_old = output_dir / "jira_data_with_score_summary.json"

        # Define output path for jira quality summary
        summary_output_path = output_dir / "jira_quality_summary_report.json"

        # Add quality_category column
        df_quality = add_quality_category(jira_data_with_llm_category_path, df_stage_filtered)

        # Generate the jira quality summary
        jira_quality_summary_json = await generate_jira_quality_summary(df_quality, summary_output_path)
        quality_summary = QualitySummary.model_validate(jira_quality_summary_json)

        # Generate jira quality summary(old way)
        df_quality["project_name"] = df_quality["issue_key"].apply(lambda x: x.split("-")[0])
        jira_quality_summaries = await generate_jira_quality_summary_legacy(df_quality)
        with open(summary_output_path_old, "w") as f:
            json.dump(jira_quality_summaries, f, indent=2)

    return PipelineDResult(
        ticket_completeness_scores=ticket_completeness_scores,
        quality_summary=quality_summary,
        jira_data_df=df_stage_filtered,  # TODO - do we need this?
    )

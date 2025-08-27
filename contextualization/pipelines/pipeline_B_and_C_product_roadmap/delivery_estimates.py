import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from otel_extensions import instrumented

from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.end_date_method04_prompt import (
    git_method04_chain,
)

# Create a logger instance for the module
logger = logging.getLogger(__name__)


def load_and_parse_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and process a DataFrame, converting date columns to UTC datetime and cleaning string values.

    Args:
        df (pd.DataFrame): Input DataFrame to process.

    Returns:
        pd.DataFrame: Processed DataFrame with cleaned strings and converted date columns.
    """
    # Make a copy to avoid modifying the original
    processed_df = df.copy()
    logger.info(
        "Processing DataFrame",
        extra={"shape": processed_df.shape, "columns": list(processed_df.columns)},
    )

    # Clean headers: strip whitespace and remove quotes
    processed_df.columns = processed_df.columns.str.strip().str.replace('"', "", regex=False)
    logger.info("Cleaned column headers", extra={"columns": list(processed_df.columns)})

    # Clean string values for object-type columns
    for col in processed_df.columns:
        if processed_df[col].dtype == "object":
            try:
                # Verify all non-null values are strings
                non_null_values = processed_df[col].dropna()
                if non_null_values.empty or non_null_values.apply(lambda x: isinstance(x, str)).all():
                    processed_df[col] = processed_df[col].str.strip().str.replace('"', "", regex=False)
                    logger.debug(f"Cleaned string values in column '{col}'")
                else:
                    logger.warning(
                        "Column contains non-string values",
                        extra={
                            "column": col,
                            "value_types": non_null_values.apply(type).value_counts().to_dict(),
                        },
                    )
            except Exception:
                logger.exception("Error cleaning string values in column", extra={"column": col})

    # Define potential date columns to convert
    date_columns = {
        "date": ["date", "Date"],
        "created": ["created", "Created", "creation_date"],
        "resolved": ["resolved", "Resolved", "resolution_date", "completed_date"],
        "updated": ["updated", "Updated", "last_updated"],
    }

    # Convert date columns to datetime with UTC
    for date_key, possible_names in date_columns.items():
        for col_name in possible_names:
            if col_name in processed_df.columns:
                try:
                    logger.info(
                        "Converting column to datetime",
                        extra={
                            "column": col_name,
                            "original_dtype": str(processed_df[col_name].dtype),
                            "sample_values": processed_df[col_name].dropna().head(3).tolist(),
                        },
                    )

                    # Attempt datetime conversion with coerce to handle invalid values
                    original_values = processed_df[col_name].copy()
                    processed_df[col_name] = pd.to_datetime(processed_df[col_name], utc=True, errors="coerce")

                    # Check for conversion issues
                    null_count = processed_df[col_name].isna().sum()
                    if null_count > 0:
                        invalid_values = original_values[processed_df[col_name].isna()].unique()
                        logger.warning(
                            "Found invalid datetime values",
                            extra={
                                "column": col_name,
                                "null_count": null_count,
                                "invalid_samples": invalid_values[:5].tolist(),
                            },
                        )

                    # Verify the resulting dtype
                    if processed_df[col_name].dtype != "datetime64[ns, UTC]":
                        logger.error(
                            "Column not converted to UTC datetime",
                            extra={
                                "column": col_name,
                                "current_dtype": str(processed_df[col_name].dtype),
                            },
                        )
                    else:
                        logger.info(
                            "Successfully converted column to datetime64[ns, UTC]",
                            extra={"column": col_name},
                        )

                    # Only process the first matching column name
                    break

                except Exception:
                    logger.exception(
                        "Error converting column to datetime",
                        extra={"column": col_name},
                    )

        else:
            logger.debug(
                "No column found for date type",
                extra={"date_key": date_key, "possible_names": possible_names},
            )

    logger.info("Processed DataFrame dtypes", extra={"dtypes": processed_df.dtypes.to_dict()})
    return processed_df


def summarize_data_for_git_initiative(git_df: pd.DataFrame, jira_df: pd.DataFrame, initiative: str) -> dict[str, Any]:
    """
    Summarize Git and Jira data for a specific Git initiative with enhanced Jira metrics
    """
    logger.info("Summarizing data for Git initiative", extra={"initiative": initiative})

    # Filter Git data by initiative
    try:
        git_initiative_data = git_df[git_df["Categorization_of_initiative_git"] == initiative]
        logger.info(
            "Git commits found for initiative",
            extra={"initiative": initiative, "commit_count": len(git_initiative_data)},
        )
    except Exception:
        logger.exception("Error filtering Git data for initiative", extra={"initiative": initiative})
        git_initiative_data = pd.DataFrame()  # Empty DataFrame as a fallback

    # Filter Jira data that might be related to this Git initiative
    try:
        # Try to match Git initiative to Jira data
        jira_initiative = jira_df[jira_df["Categorization_of_initiative_git"] == initiative]
        num_jira_tickets = len(jira_initiative)
        logger.info(
            "Jira tickets found for Git initiative",
            extra={"initiative": initiative, "ticket_count": num_jira_tickets},
        )

        if num_jira_tickets > 0:
            ticket_info = {}
            if "issue_key" in jira_initiative.columns:
                ticket_info["sample_tickets"] = jira_initiative["issue_key"].head(3).tolist()
            if "status" in jira_initiative.columns:
                ticket_info["status_counts"] = jira_initiative["status"].value_counts().to_dict()

            if ticket_info:
                logger.info(
                    "Jira ticket details for initiative",
                    extra={"initiative": initiative, **ticket_info},
                )
    except Exception:
        logger.exception(
            "Error filtering Jira data for Git initiative",
            extra={"initiative": initiative},
        )
        jira_initiative = pd.DataFrame()  # Empty DataFrame as a fallback

    # Safely summarize Git data with more Git-specific metrics
    try:
        # Calculate additional Git metrics for better estimation
        if not git_initiative_data.empty and "code" in git_initiative_data.columns:
            # Calculate code churn if available
            code_churn = (
                git_initiative_data["code"]
                .apply(
                    lambda x: (
                        sum(
                            [
                                int(line.count("+")) + int(line.count("-"))
                                for line in str(x).split("\n")
                                if line.startswith(("+", "-"))
                            ]
                        )
                        if isinstance(x, str)
                        else 0
                    )
                )
                .sum()
            )
        else:
            code_churn = 0

        # Count unique authors if available
        unique_authors = (
            git_initiative_data["name"].nunique()
            if not git_initiative_data.empty and "name" in git_initiative_data.columns
            else 0
        )

        git_summary = {
            "num_commits": len(git_initiative_data),
            "total_tik_token": (
                int(git_initiative_data["tik_tokens"].sum())
                if "tik_tokens" in git_initiative_data.columns
                and not git_initiative_data["tik_tokens"].isna().all()
                and len(git_initiative_data) > 0
                else 0
            ),
            "date_range": (
                f"{git_initiative_data['date'].min()} to {git_initiative_data['date'].max()}"
                if not git_initiative_data.empty and "date" in git_initiative_data.columns
                else "N/A"
            ),
            "unique_files": (
                list(git_initiative_data["files"].value_counts().head(10).index)
                if "files" in git_initiative_data.columns and not git_initiative_data.empty
                else []
            ),
            "code_churn": code_churn,
            "unique_authors": unique_authors,
            "commit_frequency": (
                len(git_initiative_data)
                / max(
                    1,
                    (git_initiative_data["date"].max() - git_initiative_data["date"].min()).days,
                )
                if not git_initiative_data.empty and "date" in git_initiative_data.columns
                else 0
            ),
            "repositories": (
                list(git_initiative_data["repository"].unique())
                if not git_initiative_data.empty and "repository" in git_initiative_data.columns
                else []
            ),
            "commit_messages": (
                list(git_initiative_data["Summary"].head(10))
                if not git_initiative_data.empty and "Summary" in git_initiative_data.columns
                else []
            ),
            "purpose_of_changes": (
                git_initiative_data["Purpose_of_change"].value_counts().to_dict()
                if not git_initiative_data.empty and "Purpose_of_change" in git_initiative_data.columns
                else {}
            ),
            "impact_on_product": (
                git_initiative_data["Impact_on_product"].value_counts().to_dict()
                if not git_initiative_data.empty and "Impact_on_product" in git_initiative_data.columns
                else {}
            ),
        }
    except Exception:
        logger.exception(
            "Error summarizing Git data for initiative",
            extra={"initiative": initiative},
        )
        git_summary = {
            "num_commits": 0,
            "total_tik_token": 0,
            "date_range": "N/A",
            "unique_files": [],
            "code_churn": 0,
            "unique_authors": 0,
            "commit_frequency": 0,
            "repositories": [],
            "commit_messages": [],
            "purpose_of_changes": {},
            "impact_on_product": {},
        }

    # Enhanced Jira summary with more detailed metrics
    try:
        if not jira_initiative.empty:
            # Calculate ticket completion metrics
            completed_statuses = ["Done", "Closed", "Resolved", "Completed", "Fixed"]
            # Default to status column, but try other common status column names if not found
            status_col = "status"
            if status_col not in jira_initiative.columns:
                potential_status_cols = ["Status", "ticket_status", "issue_status"]
                for col in potential_status_cols:
                    if col in jira_initiative.columns:
                        status_col = col
                        break

            if status_col in jira_initiative.columns:
                # Calculate status breakdown
                status_counts = jira_initiative[status_col].value_counts().to_dict()

                # Calculate completion percentage
                completed_tickets = jira_initiative[
                    jira_initiative[status_col].str.lower().isin([s.lower() for s in completed_statuses])
                ]
                completion_percentage = (
                    len(completed_tickets) / len(jira_initiative) * 100 if len(jira_initiative) > 0 else 0
                )
            else:
                status_counts = {}
                completion_percentage = 0
                completed_tickets = pd.DataFrame()

            # Check for story points
            story_point_cols = [
                "story_points",
                "Story_Points",
                "points",
                "Points",
                "story points",
            ]
            story_point_col = None
            for col in story_point_cols:
                if col in jira_initiative.columns:
                    story_point_col = col
                    break

            if story_point_col:
                # Calculate story point metrics
                total_story_points = jira_initiative[story_point_col].sum()
                completed_story_points = completed_tickets[story_point_col].sum() if not completed_tickets.empty else 0
                story_point_velocity = None

                # Try to calculate story point velocity if we have dates
                if "created" in jira_initiative.columns and len(completed_tickets) > 0:
                    # Calculate time range in weeks
                    earliest_date = jira_initiative["created"].min()
                    latest_date = jira_initiative["created"].max()
                    time_range_weeks = max(1, (latest_date - earliest_date).days / 7)

                    # Calculate velocity: completed points / time range in weeks
                    story_point_velocity = completed_story_points / time_range_weeks
            else:
                total_story_points = 0
                completed_story_points = 0
                story_point_velocity = None

            # Try to calculate average resolution time
            created_col = next(
                (col for col in ["created", "Created", "creation_date"] if col in jira_initiative.columns),
                None,
            )
            resolved_col = next(
                (
                    col
                    for col in [
                        "resolved",
                        "Resolved",
                        "resolution_date",
                        "completed_date",
                    ]
                    if col in jira_initiative.columns
                ),
                None,
            )

            if created_col and resolved_col:
                # Filter tickets with both creation and resolution dates
                resolved_tickets = jira_initiative.dropna(subset=[resolved_col])
                if not resolved_tickets.empty:
                    # Calculate average resolution time in days
                    resolution_times = resolved_tickets[resolved_col] - resolved_tickets[created_col]
                    avg_resolution_days = resolution_times.mean().total_seconds() / (24 * 3600)

                    # Calculate resolution time percentiles for better understanding
                    p25_resolution_days = resolution_times.quantile(0.25).total_seconds() / (24 * 3600)
                    p50_resolution_days = resolution_times.quantile(0.50).total_seconds() / (24 * 3600)
                    p75_resolution_days = resolution_times.quantile(0.75).total_seconds() / (24 * 3600)
                else:
                    avg_resolution_days = 0
                    p25_resolution_days = 0
                    p50_resolution_days = 0
                    p75_resolution_days = 0
            else:
                avg_resolution_days = 0
                p25_resolution_days = 0
                p50_resolution_days = 0
                p75_resolution_days = 0

            # Extract ticket types if available
            type_col = next(
                (col for col in ["type", "Type", "issue_type", "ticket_type"] if col in jira_initiative.columns),
                None,
            )
            type_breakdown = jira_initiative[type_col].value_counts().to_dict() if type_col else {}

            # Extract components if available
            component_col = next(
                (col for col in ["component", "Component", "components"] if col in jira_initiative.columns),
                None,
            )
            components = list(jira_initiative[component_col].unique()) if component_col else []

            # Extract label information if available
            label_col = next(
                (col for col in ["labels", "Labels", "label"] if col in jira_initiative.columns),
                None,
            )
            if label_col and not jira_initiative[label_col].isna().all():
                # Handle cases where labels might be stored as lists or strings
                all_labels = []
                for labels in jira_initiative[label_col].dropna():
                    if isinstance(labels, list):
                        all_labels.extend(labels)
                    elif isinstance(labels, str):
                        # Try to parse JSON if it's a string representation of a list
                        try:
                            parsed_labels = json.loads(labels.replace("'", '"'))
                            if isinstance(parsed_labels, list):
                                all_labels.extend(parsed_labels)
                            else:
                                all_labels.append(labels)
                        except Exception as e:
                            logger.warning("Labels are not in JSON format: %s", e)
                            # If it's not JSON, treat as a single label or comma-separated list
                            if "," in labels:
                                all_labels.extend([label.strip() for label in labels.split(",")])
                            else:
                                all_labels.append(labels)

                label_counts = {}
                for label in all_labels:
                    label_counts[label] = label_counts.get(label, 0) + 1
            else:
                label_counts = {}

            # Build comprehensive Jira summary
            jira_summary = {
                "num_tickets": len(jira_initiative),
                "ticket_ids": (
                    list(jira_initiative["issue_key"].unique())[:20] if "issue_key" in jira_initiative.columns else []
                ),
                "status_counts": status_counts,
                "completion_percentage": completion_percentage,
                "total_story_points": total_story_points,
                "completed_story_points": completed_story_points,
                "story_point_velocity": story_point_velocity,
                "average_resolution_days": avg_resolution_days,
                "resolution_percentiles": {
                    "p25_days": p25_resolution_days,
                    "p50_days": p50_resolution_days,
                    "p75_days": p75_resolution_days,
                },
                "priority_breakdown": (
                    jira_initiative["priority"].value_counts().to_dict()
                    if "priority" in jira_initiative.columns
                    else {}
                ),
                "issue_type_breakdown": type_breakdown,
                "components": components,
                "labels": label_counts,
                "assignees": (
                    list(jira_initiative["assignee"].unique()) if "assignee" in jira_initiative.columns else []
                ),
                "creation_date_range": (
                    f"{jira_initiative['created'].min()} to {jira_initiative['created'].max()}"
                    if "created" in jira_initiative.columns
                    else "N/A"
                ),
                "latest_update": (
                    jira_initiative["updated"].max()
                    if "updated" in jira_initiative.columns and not jira_initiative["updated"].isna().all()
                    else "N/A"
                ),
                "average_lifecycle_days": (
                    (jira_initiative["updated"] - jira_initiative["created"]).mean().total_seconds() / (24 * 3600)
                    if "updated" in jira_initiative.columns and "created" in jira_initiative.columns
                    else 0
                ),
            }
        else:
            # No Jira tickets found for this initiative
            jira_summary = {
                "num_tickets": 0,
                "ticket_ids": [],
                "status_counts": {},
                "completion_percentage": 0,
                "total_story_points": 0,
                "completed_story_points": 0,
                "story_point_velocity": None,
                "average_resolution_days": 0,
                "resolution_percentiles": {
                    "p25_days": 0,
                    "p50_days": 0,
                    "p75_days": 0,
                },
                "priority_breakdown": {},
                "issue_type_breakdown": {},
                "components": [],
                "labels": {},
                "assignees": [],
                "creation_date_range": "N/A",
                "latest_update": "N/A",
                "average_lifecycle_days": 0,
            }
    except Exception:
        logger.exception(
            "Error creating enhanced Jira summary for Git initiative",
            extra={"initiative": initiative},
        )
        # Fall back to basic Jira summary
        jira_summary = {
            "num_tickets": len(jira_initiative) if not jira_initiative.empty else 0,
            "ticket_ids": [],
            "status_counts": {},
            "average_lifecycle_days": 0,
        }

    return {"git_summary": git_summary, "jira_summary": jira_summary}


def normalize_initiative_name(name: str | None) -> str:
    """
    Normalize initiative names for better matching
    """
    if not name:
        return ""
    try:
        # Convert to lowercase and remove special characters
        return "".join(c.lower() for c in str(name) if c.isalnum() or c.isspace()).strip()
    except Exception:
        return ""


@instrumented
async def append_git_delivery_estimates(
    git_df: pd.DataFrame,
    jira_df: pd.DataFrame,
    git_updated_initiatives: dict[str, Any],
    git_initiatives_json_path: Path,
) -> dict[str, Any] | None:
    """
    Process Git and Jira data to generate delivery estimates directly for initiatives in the JSON file
    """
    logger.info("Appending delivery estimates to Git initiatives")

    try:
        if not git_updated_initiatives:
            logger.error("Git initiatives not found")
            return None

        # Clean and process dataframes
        try:
            processed_git_df = load_and_parse_csv(git_df)
            logger.info(
                "Processed Git data",
                extra={
                    "rows": processed_git_df.shape[0],
                    "columns": processed_git_df.shape[1],
                },
            )
        except Exception:
            logger.exception("Error processing Git data")
            processed_git_df = git_df.copy()  # Use original as fallback

        try:
            processed_jira_df = load_and_parse_csv(jira_df)
            logger.info(
                "Processed Jira data",
                extra={
                    "rows": processed_jira_df.shape[0],
                    "columns": processed_jira_df.shape[1],
                },
            )
        except Exception:
            logger.exception("Error processing Jira data")
            processed_jira_df = jira_df.copy()  # Use original as fallback

        # Prepare batch requests for all initiatives
        current_date = datetime.now().strftime("%Y-%m-%d")
        initiatives = git_updated_initiatives.get("initiatives", [])

        # Prepare summaries and batch inputs
        batch_inputs = []
        for initiative in initiatives:
            initiative_name = initiative.get("initiative_name", "")
            logger.info(
                "Preparing batch input for Git initiative",
                extra={"initiative": initiative_name},
            )

            try:
                # Summarize data for this specific initiative
                summary = summarize_data_for_git_initiative(processed_git_df, processed_jira_df, initiative_name)
                batch_inputs.append(
                    {
                        "summary_data": json.dumps(summary, default=str),
                        "initiative": initiative_name,
                        "current_date": current_date,
                    }
                )
            except Exception:
                logger.exception(
                    "Error preparing batch input for Git initiative",
                    extra={"initiative": initiative_name},
                )

        # Generate estimates using batch processing
        try:
            if batch_inputs:
                estimates = await git_method04_chain.abatch(batch_inputs)

                # Assign estimates back to initiatives
                for estimate, initiative in zip(estimates, initiatives):
                    initiative["delivery_estimate"] = estimate

        except Exception:
            logger.exception("Error during batch processing assigning delivery estimates")
            for initiative in initiatives:
                if "delivery_estimate" in initiative:
                    continue
                initiative["delivery_estimate"] = None

        # Save the updated initiatives data
        with open(git_initiatives_json_path, "w") as f:
            json.dump(git_updated_initiatives, f, indent=4)

        logger.info(
            "Successfully appended delivery estimates to Git initiatives",
            extra={"json_path": git_initiatives_json_path},
        )

    except Exception:
        logger.exception(
            "Error appending delivery estimates to Git initiatives",
            extra={"json_path": git_initiatives_json_path},
        )

    return git_updated_initiatives

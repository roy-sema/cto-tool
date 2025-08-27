import json
import logging
from collections import defaultdict
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
    final_summary_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.jira_ticket_categorization_prompt import (
    categorize_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.prompts.stage_category_prompt import (
    stage_classification_chain,
)
from contextualization.pipelines.pipeline_D_jira_score_completeness.schemas import (
    JiraTicketData,
    PipelineDResult,
    QualitySummary,
    TicketCompletenessScoreResult,
    categorize_quality,
)
from contextualization.utils.vcr_mocks import calls_context

logger = logging.getLogger(__name__)


token_limit = conf["llms"][llm_name]["token_limit"]
batch_threshold = conf["llms"][llm_name]["batch_threshold"]


def dataframe_to_jira_tickets(df: pd.DataFrame) -> list[JiraTicketData]:
    """Convert pandas DataFrame to list of JiraTicketData models."""
    tickets = []
    for _, row in df.iterrows():
        ticket = JiraTicketData(
            issue_key=row["issue_key"],
            summary=row["summary"],
            project_name=row["issue_key"].split("-")[0],
            issue_type=row.get("Issue Type"),
            components=row.get("components"),
            description=row.get("description"),
            priority=row.get("priority"),
            labels=row.get("labels"),
            attachment=row.get("attachment"),
            issuelinks=row.get("issuelinks"),
            assignee=row.get("assignee"),
            status=row.get("status"),
            created=row.get("created"),
        )
        tickets.append(ticket)
    return tickets


@instrumented
async def assign_jira_completeness_score(jira_tickets: list[JiraTicketData]) -> list[JiraTicketData]:
    logger.info("Processing Jira completeness score", extra={"jira_ticket_count": len(jira_tickets)})
    results = await jira_completeness_score_chain.abatch(
        [{"jira_ticket_row": ticket.format_ticket_for_completeness_score()} for ticket in jira_tickets]
    )

    # Update the original tickets with the scores
    for i, ticket in enumerate(jira_tickets):
        result = results[i]
        ticket.jira_completeness_score = result.jira_completeness_score
        ticket.evaluation_jira_completeness_score = result.evaluation_jira_completeness_score
        ticket.explanation_jira_completeness_score = result.explanation_jira_completeness_score
        ticket.quality_category = categorize_quality(ticket.jira_completeness_score)

    # todo think of deepcopy
    return jira_tickets


def summarize_by_field(tickets: list[JiraTicketData], field: str) -> list[dict]:
    grouped = defaultdict(list)
    for ticket in tickets:
        field_value = getattr(ticket, field)
        grouped[field_value].append(ticket.jira_completeness_score)

    results = []
    for field_value, scores in grouped.items():
        average_count = round(sum(scores) / len(scores), 2)
        quality_category = categorize_quality(average_count)
        results.append(
            {
                field: field_value,
                "ticket_count": len(scores),
                "average_count": average_count,
                "quality_category": quality_category,
            }
        )

    return results


@instrumented
async def generate_jira_quality_summary(jira_tickets: list[JiraTicketData]) -> dict[str, Any]:
    projects_grouped = defaultdict(list)
    for ticket in jira_tickets:
        projects_grouped[ticket.project_name].append(ticket)

    final_summary_inputs = []
    for project, tickets in projects_grouped.items():
        scores = [ticket.jira_completeness_score for ticket in tickets]
        avg_score = round(sum(scores) / len(scores), 2)
        sorted_tickets = sorted(tickets, key=lambda t: t.jira_completeness_score, reverse=True)
        top_3 = [t.get_dict_for_summary() for t in sorted_tickets[:3]]
        bottom_3 = [t.get_dict_for_summary() for t in sorted_tickets[-3:]]

        sample_tickets = {"top_3": top_3, "bottom_3": bottom_3}

        by_stage = summarize_by_field(tickets, "stage_category")
        by_category = summarize_by_field(tickets, "llm_category")

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
                # there is a workaround involving pydantic_v1, so using old method for jsonable dict
                "key_findings": json.loads(key_findings[i].json()),
            }
        )

    all_scores = [ticket.jira_completeness_score for ticket in jira_tickets]
    project_names = list(projects_grouped.keys())
    overall = {
        "total_projects": len(project_names),
        "project_names": sorted(project_names),
        "average_score": round(sum(all_scores) / len(all_scores), 2),
        "by_stage": summarize_by_field(jira_tickets, "stage_category"),
        "by_category": summarize_by_field(jira_tickets, "llm_category"),
    }

    complete_summary = {"all_projects": overall, "by_project": by_project}

    return complete_summary


@instrumented
async def categorise_jira_tickets(tickets: list[JiraTicketData]) -> list[JiraTicketData]:
    logger.info(f"Processing {len(tickets)} tickets")
    # Prepare batch inputs - one input dict per ticket
    batch_inputs = []
    indices_to_update = []

    for idx, ticket in enumerate(tickets):
        text = ticket.description
        if not text or not text.strip():
            logger.warning(f"No description found for ticket {ticket.issue_key}, defaulting to category OTHER")
            ticket.llm_category = TicketCategory.OTHER
        else:
            indices_to_update.append(idx)
            batch_inputs.append({"jira_ticket_row": text})

    if not indices_to_update:
        return tickets  # All were empty

    responses = await categorize_chain.abatch(batch_inputs)

    for idx, response in zip(indices_to_update, responses):
        tickets[idx].llm_category = response.llm_category

    return tickets


@instrumented
async def assign_stages_from_ticket_statuses(jira_tickets: list[JiraTicketData]) -> list[JiraTicketData]:
    unique_statuses = set()
    for ticket in jira_tickets:
        unique_statuses.add(ticket.status.strip().lower())

    logger.info("Inferring stage categories using language model.")
    category_mappings = await stage_classification_chain.ainvoke({"jira_ticket_stages": unique_statuses})

    final_mappings = {
        category_mapping.original_stage: category_mapping.category
        for category_mapping in category_mappings.stage_categories
    }

    for ticket in jira_tickets:
        ticket.stage_category = final_mappings[ticket.status.strip().lower()]

    return jira_tickets


async def run_jira_completeness_score_pipeline(
    jira_url: str | None = None,
    confluence_user: str | None = None,
    confluence_token: str | None = None,
    jira_access_token: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    jira_project_names: list[str] | None = None,
) -> PipelineDResult | None:
    logger.info(
        f"Running pipeline D with params: {jira_url=} {confluence_user=} confluence_token=<REDACTED> "
        f"jira_access_token=<REDACTED> {start_date=} {end_date=} {jira_project_names=}"
    )
    with calls_context("pipeline_d.yaml"):
        start_date = start_date.split("T")[0] if start_date else None
        end_date = end_date.split("T")[0] if end_date else None

        if not jira_project_names:
            logger.info("No JIRA project selected provided.")
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
            logger.warning("Pipeline Jira completeness score - No JIRA data found. Exiting.")
            return None

        # Convert DataFrame to pydantic models
        jira_tickets = dataframe_to_jira_tickets(df)

        scored_tickets = await assign_jira_completeness_score(jira_tickets)

        staged_tickets = await assign_stages_from_ticket_statuses(scored_tickets)

        llm_categorised_tickets = await categorise_jira_tickets(staged_tickets)

        # keeping backward compatibility with anomaly insights pipeline
        jira_data_df = pd.DataFrame(
            [{**ticket.model_dump(), "Issue Type": ticket.issue_type} for ticket in llm_categorised_tickets]
        )

        ticket_completeness_scores = []
        for ticket in llm_categorised_tickets:
            score_result = TicketCompletenessScoreResult(
                issue_key=ticket.issue_key,
                summary=ticket.summary,
                description=ticket.description,
                priority=ticket.priority,
                jira_completeness_score=ticket.jira_completeness_score,
                evaluation_jira_completeness_score=ticket.evaluation_jira_completeness_score,
                explanation_jira_completeness_score=ticket.explanation_jira_completeness_score,
                stage_category=ticket.stage_category,
                llm_category=ticket.llm_category,
                project_name=ticket.project_name,
                assignee=ticket.assignee,
                quality_category=ticket.quality_category,
            )
            ticket_completeness_scores.append(score_result)

        filtered_tickets = [
            ticket
            for ticket in llm_categorised_tickets
            if ticket.stage_category
            not in {
                StageCategory.DONE.value,
                StageCategory.WILL_NOT_DO.value,
                StageCategory.BACKLOG.value,
            }
        ]

        if not filtered_tickets:
            logger.warning(
                "Pipeline D Jira completeness score - Can not generate further insights: NO data in 'To Do', 'In Progress' stages"
            )
            return PipelineDResult(ticket_completeness_scores=ticket_completeness_scores, jira_data_df=jira_data_df)

        jira_quality_summary_json = await generate_jira_quality_summary(filtered_tickets)
        quality_summary = QualitySummary.model_validate(jira_quality_summary_json)

    return PipelineDResult(
        ticket_completeness_scores=ticket_completeness_scores,
        quality_summary=quality_summary,
        jira_data_df=jira_data_df,
    )

import logging
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict

from contextualization.models.ticket_completeness import StageCategory, TicketCategory

logger = logging.getLogger(__name__)


class QualitySummaryStage(StrEnum):
    DONE = "Done"
    WILL_NOT_DO = "Will Not Do"
    UNDERWAY = "Underway"
    READY_FOR_WORK = "Ready for Work"
    BACKLOG = "Backlog"


class QualityCategory(StrEnum):
    INITIAL = "Initial"
    EMERGING = "Emerging"
    MATURE = "Mature"
    ADVANCED = "Advanced"
    UNCATEGORIZED = "Uncategorized"


QUALITY_THRESHOLDS = {
    QualityCategory.INITIAL: 25,
    QualityCategory.EMERGING: 50,
    QualityCategory.MATURE: 75,
    QualityCategory.ADVANCED: 100,
}


def categorize_quality(score: int | float) -> QualityCategory:
    if score < 0 or score > 100:
        logger.exception("Invalid score value", extra={"score": score})
        return QualityCategory.UNCATEGORIZED.value

    for category, threshold in QUALITY_THRESHOLDS.items():
        if score <= threshold:
            return category.value

    return QualityCategory.UNCATEGORIZED.value


class TicketCompletenessScoreResult(BaseModel):
    issue_key: str
    summary: str
    description: str | None = None
    priority: str
    jira_completeness_score: int
    evaluation_jira_completeness_score: str
    explanation_jira_completeness_score: str
    # we assign these categories as different ticket management systems might have different names for
    # the same
    stage_category: StageCategory
    llm_category: TicketCategory
    project_name: str
    assignee: str | None = None
    quality_category: QualityCategory


class StageSummary(BaseModel):
    stage: str
    ticket_count: int
    average_count: float
    quality_category: QualityCategory


class CategorySummary(BaseModel):
    category: TicketCategory
    ticket_count: int
    average_count: float
    quality_category: QualityCategory


class SampleTicket(BaseModel):
    issue_key: str
    jira_completeness_score: int
    stage_category: StageCategory
    llm_category: TicketCategory
    quality_category: QualityCategory
    explanation_jira_completeness_score: str


class SampleTickets(BaseModel):
    top_3: list[SampleTicket]
    bottom_3: list[SampleTicket]


class KeyFindings(BaseModel):
    overview: str
    key_findings: list[str]
    overall_assessment: str
    prioritized_recommendations: list[str]


class ProjectSummary(BaseModel):
    project: str
    sample_tickets: SampleTickets
    average_score: float
    by_stage: list[StageSummary]
    by_category: list[CategorySummary]
    key_findings: KeyFindings


class AllProjectsSummary(BaseModel):
    total_projects: int
    project_names: list[str]
    average_score: float
    by_stage: list[StageSummary]
    by_category: list[CategorySummary]


class QualitySummary(BaseModel):
    all_projects: AllProjectsSummary
    by_project: list[ProjectSummary]


class PipelineDResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    ticket_completeness_scores: list[TicketCompletenessScoreResult]
    quality_summary: QualitySummary | None = None
    jira_data_df: pd.DataFrame  # TODO - do we really need this?

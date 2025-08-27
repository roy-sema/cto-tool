import logging
from datetime import datetime
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from contextualization.models.ticket_completeness import StageCategory, TicketCategory

logger = logging.getLogger(__name__)


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


def categorize_quality(score: float) -> QualityCategory:
    if score < 0 or score > 100:
        logger.exception("Invalid score value", extra={"score": score})
        return QualityCategory.UNCATEGORIZED

    for category, threshold in QUALITY_THRESHOLDS.items():
        if score <= threshold:
            return category

    return QualityCategory.UNCATEGORIZED


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
    stage: str = Field(alias="stage_category")
    ticket_count: int
    average_count: float
    quality_category: QualityCategory


class CategorySummary(BaseModel):
    category: TicketCategory = Field(alias="llm_category")
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


class JiraTicketData(BaseModel):
    model_config = ConfigDict(use_enum_values=True, revalidate_instances="always")

    issue_key: str
    summary: str
    issue_type: str
    components: list

    priority: str
    project_name: str
    status: str
    created: datetime
    labels: list
    attachment: list
    issuelinks: list
    assignee: str | None = None
    description: str | None = None

    jira_completeness_score: int | None = None
    evaluation_jira_completeness_score: str | None = None
    explanation_jira_completeness_score: str | None = None
    stage_category: StageCategory | None = None
    llm_category: TicketCategory | None = None
    quality_category: QualityCategory | None = None

    # necessary for jira_anomaly_driven_insights pipeline
    parsed_changelog: list[dict] | None = None
    updated: datetime | None = None

    def get_dict_for_summary(self) -> dict:
        return {
            "issue_key": self.issue_key,
            "jira_completeness_score": self.jira_completeness_score,
            "stage_category": self.stage_category.value,
            "llm_category": self.llm_category.value,
            "quality_category": self.quality_category.value,
            "explanation_jira_completeness_score": self.explanation_jira_completeness_score,
        }

    def format_ticket_for_completeness_score(self) -> str:
        selected_fields = [
            "issue_key",
            "summary",
            "issue_type",
            "components",
            "description",
            "priority",
            "labels",
            "attachment",
            "issuelinks",
            "assignee",
            "status",
        ]
        column_names = " | ".join(selected_fields)
        values = []
        for field in selected_fields:
            value = getattr(self, field, None)
            values.append(str(value) if value is not None else "")
        formatted_ticket = column_names + "\n" + " | ".join(values).replace("\n", " ")

        return formatted_ticket


class PipelineDResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    ticket_completeness_scores: list[TicketCompletenessScoreResult]
    quality_summary: QualitySummary | None = None
    jira_data_df: pd.DataFrame

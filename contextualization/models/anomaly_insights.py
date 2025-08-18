from enum import StrEnum

from pydantic import BaseModel

from contextualization.pipelines.insights_aggregation_pipeline.schemas import SkipMeetingInsights


class ConfidenceLevel(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class InsightCategory(StrEnum):
    TIMELINE_IMPACT = "timeline_impact"
    QUALITY_IMPACT = "quality_impact"
    SCOPE_IMPACT = "scope_impact"
    RESOURCE_IMPACT = "resource_impact"
    TECHNICAL_IMPACT = "technical_impact"
    FEATURE_ADDITION = "feature_addition"
    FEATURE_ENHANCEMENT = "feature_enhancement"
    SECURITY_IMPACT = "security_impact"
    OTHER = "other"


class JiraInsight(BaseModel):
    unique_id: str | None = None
    project: str
    category: InsightCategory
    title: str
    insight: str
    evidence: str
    significance_score: int
    confidence_level: ConfidenceLevel
    source: list[str]
    ticket_categories: list[str]


class JiraCombinedInsights(BaseModel):
    anomaly_insights: list[JiraInsight]
    skip_meeting_insights: SkipMeetingInsights


class Message(BaseModel):
    audience: str
    message_for_audience: str


class BlindSpot(BaseModel):
    location: str
    resolution: str


class GitInsight(BaseModel):
    unique_id: str | None = None
    repo: str
    category: InsightCategory
    title: str
    insight: str
    evidence: str
    significance_score: int
    confidence_level: ConfidenceLevel
    sources: list[str]
    resolution: str
    messages: list[Message]
    blind_spot: BlindSpot


class GitCombinedInsights(BaseModel):
    anomaly_insights: list[GitInsight]

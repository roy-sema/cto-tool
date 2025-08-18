from pydantic import BaseModel


class Message(BaseModel):
    audience: str
    message_for_audience: str


class Insight(BaseModel):
    unique_id: str | None = None
    project_name: str
    category: str
    title: str
    insight: str
    evidence: str
    significance_score: int
    confidence_level: str
    source: list[str]
    ticket_categories: list[str]
    resolution: str | None = None
    messages: list[Message] | None = None


class SkipMeetingInsights(BaseModel):
    anomaly_insights: list[Insight]


class FileEntry(BaseModel):
    file_name: str
    branch_name: str
    commit_id: str


class BlindSpot(BaseModel):
    location: str
    resolution: str


class DetailInsight(BaseModel):
    unique_id: str
    title: str
    category: str
    insight: str
    evidence: str
    significance_score: float
    confidence_level: str
    sources: list[str]
    source: list[str]
    files: list[FileEntry] | None = None
    blind_spot: BlindSpot | None = None
    resolution: str
    messages: list[Message] | None = None
    ticket_categories: list[str]
    project_name: str
    repo: str


class GroupOfInsights(BaseModel):
    similar_insight_ids: list[str]
    similarity_reason: str
    details_of_insights: list[DetailInsight]


class InsightsAggregation(BaseModel):
    groups_of_insights: list[GroupOfInsights]
    summary: str

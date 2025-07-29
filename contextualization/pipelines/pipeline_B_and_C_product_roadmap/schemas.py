from datetime import date

from pydantic import BaseModel


class AdditionalDataNeeds(BaseModel):
    confidence_impact: str
    data_gaps: list[str]
    suggested_tracking_improvements: list[str]


class CalculationMethod(BaseModel):
    data_sources_used: list[str]
    formulas_applied: list[str]
    key_metrics_used: list[str]
    primary_calculation_approach: str


class DataRelationshipAssessment(BaseModel):
    data_coverage: float
    key_relationship_gaps: str
    relationship_strength: str


class DeliveryAcceleration(BaseModel):
    highest_impact_recommendations: list[str]
    process_improvements: list[str]
    resource_considerations: list[str]
    scope_considerations: list[str]


class ExecutiveSummary(BaseModel):
    confidence_level: str
    estimated_completion_date: date
    estimated_range: str
    primary_factors: str


class VelocityAnalysis(BaseModel):
    complexity_assessment: str
    historical_velocity: str
    team_capacity_factors: str


class DeliveryEstimate(BaseModel):
    additional_data_needs: AdditionalDataNeeds
    calculation_method: CalculationMethod
    data_relationship_assessment: DataRelationshipAssessment
    delivery_acceleration: DeliveryAcceleration
    executive_summary: ExecutiveSummary
    initiative_name: str
    velocity_analysis: VelocityAnalysis


class Epic(BaseModel):
    epic_description: str
    epic_name: str
    epic_percentage: int


class Initiative(BaseModel):
    delivery_estimate: DeliveryEstimate | None = None
    initiative_name: str
    epics: list[Epic]
    estimated_end_date: date | None = None
    expedited_delivery_date: date | None = None
    initiative_description: str
    initiative_name: str
    initiative_percentage: int
    number_ticket_done: int | None = None
    percentage_tickets_done: int | None = None
    recommendation_insight: str | None = None
    start_date: date | None = None
    total_tickets: int | None = None


class GitInitiatives(BaseModel):
    initiatives: list[Initiative]
    summary: str | None = None


class Insight(BaseModel):
    git_activity: str
    jira_activity: str
    needs_reconciliation: bool
    work_group: str
    work_group_type: str


class Insights(BaseModel):
    insights: list[Insight]


class PipelineBCResultItem(BaseModel):
    git_initiatives: GitInitiatives
    insights: Insights | None = None


class PipelineBCResult(BaseModel):
    items: dict[str, PipelineBCResultItem]

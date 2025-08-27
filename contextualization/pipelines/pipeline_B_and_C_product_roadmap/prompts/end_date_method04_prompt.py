from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.tags import get_tags_prompt
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser


# Pydantic Models for Output Structure
class ExecutiveSummary(BaseModel):
    estimated_completion_date: str = Field(description="Estimated completion date in YYYY-MM-DD format")
    confidence_level: str = Field(description="Confidence level: High/Medium/Low")
    estimated_range: str = Field(
        description="Range of possible completion dates in format <'YYYY-MM-DD' to 'YYYY-MM-DD'>"
    )
    primary_factors: str = Field(description="Brief summary of key factors influencing the estimate")


class CalculationMethod(BaseModel):
    data_sources_used: list[str] = Field(description="List of data sources used")
    primary_calculation_approach: str = Field(description="Description of estimation methodology")
    key_metrics_used: list[str] = Field(description="List of metrics with values")
    formulas_applied: list[str] = Field(description="Formulas used in calculations")


class DataRelationshipAssessment(BaseModel):
    data_coverage: float = Field(description="Percentage of initiative tracked across systems")
    relationship_strength: str = Field(description="Strength of relationships: Strong/Moderate/Weak")
    key_relationship_gaps: str = Field(description="Description of missing connections")


class VelocityAnalysis(BaseModel):
    historical_velocity: str = Field(description="Metrics used with actual values")
    team_capacity_factors: str = Field(description="Considerations with data points")
    complexity_assessment: str = Field(description="Rating and rationale. [FORMAT_AS_BULLET_POINTS]")


class DeliveryAcceleration(BaseModel):
    highest_impact_recommendations: list[str] = Field(description="Specific actions with estimated time savings")
    resource_considerations: list[str] = Field(description="Specific suggestions")
    process_improvements: list[str] = Field(description="Actionable recommendations")
    scope_considerations: list[str] = Field(description="Potential adjustments")


class AdditionalDataNeeds(BaseModel):
    data_gaps: list[str] = Field(description="Missing information that would improve estimates")
    suggested_tracking_improvements: list[str] = Field(description="How to collect better data")
    confidence_impact: str = Field(description="How additional data would affect estimate confidence")


class InitiativeEstimate(BaseModelThatRemovesTags):
    initiative_name: str = Field(description="Name of the roadmap initiative")
    executive_summary: ExecutiveSummary
    calculation_method: CalculationMethod
    data_relationship_assessment: DataRelationshipAssessment
    velocity_analysis: VelocityAnalysis
    delivery_acceleration: DeliveryAcceleration
    additional_data_needs: AdditionalDataNeeds


# Prompt Template for Git-focused Initiative Estimation
git_system_template = """You are an expert in software development analytics tasked with estimating completion dates for roadmap initiatives based primarily on Git data, with supporting Jira data when available. Analyze the summarized Git and Jira data to estimate the completion date for the Git initiative: {initiative}.

**Summarized Data (JSON)**: <json>{summary_data}</json>  
**Current Date**: {current_date}

Your responsibilities include:
1. **Git-Focused Relationship Mapping with Jira Integration**:
   - Analyze Git commit patterns including frequency, velocity, and code churn
   - Extract semantic meaning from commit messages, branch names, and file paths
   - Identify work patterns including bursts of activity and quiet periods
   - Use repository structure and file changes to infer technical complexity
   - When available, use Jira ticket data to validate and enhance your understanding
   - If Jira data is present, incorporate ticket status, story points, and resolution times
   - Assign a confidence level (High/Medium/Low) to each relationship

2. **Historical Pattern Analysis**:
   - Calculate baseline velocity from Git commit frequency, volume and complexity
   - If Jira data is available, incorporate ticket completion rates and story point velocity
   - Analyze code churn (lines added/modified/deleted) to evaluate work complexity
   - Examine file change patterns to identify component-level progress
   - Use commit timestamps to determine development cadence and rhythms

3. **Complexity Evaluation**:
   - Assess technical complexity using tik_token count, code churn, and unique_files
   - If Jira data is available, consider ticket complexity indicated by story points
   - Evaluate architectural complexity based on file locations, dependencies, and change patterns
   - Consider the number of unique files changed as an indicator of scope
   - Use commit message semantics to identify challenging implementation areas

4. **Timeline Estimation**:
   - Estimate base timeline using Git commit velocity and observed delivery pace
   - If Jira data shows ticket completion rates, incorporate this into your timeline calculation
   - Apply complexity multipliers based on technical factors observed in Git data
   - Add contingency (e.g., +0.5x) based on data quality or relationship uncertainty
   - Output three timeline scenarios:
     - **Optimistic**: 80% of expected
     - **Expected**: baseline + complexity + contingency
     - **Pessimistic**: 120% of expected
   - Round dates to nearest full day and use YYYY-MM-DD format
   - Estimation granularity is days.
   - Ensure that dates are not formed using simple logic like "in 10 days","in 2 weeks", "middle of the month" or "in 2 months", but rather using the actual amount of days.
   - If estimate date appears to be more than 2 months away, add a 1 month contingency

5. **Delivery Acceleration Opportunities**:
   - Identify patterns in the Git and Jira data that suggest bottlenecks or inefficiencies
   - Suggest task parallelization opportunities based on file change patterns
   - Recommend potential code reuse based on repository structure analysis
   - Suggest scope refinements based on observed implementation complexity
   - Identify process improvements based on development workflow patterns

6. **Additional Data Gaps**:
   - Explicitly note when Git or Jira data is insufficient for high-confidence estimates
   - State how additional Git or Jira metrics would improve estimates
   - Suggest complementary data that would strengthen the analysis

**Output Instructions**:
- Generate a well-structured JSON object following the given Pydantic model
- When Jira data is present, be sure to mention it in your data_sources_used list
- If Jira data is absent or limited, note this in key_relationship_gaps
- Include all required fields:
  - initiative_name
  - executive_summary
  - calculation_method
  - data_relationship_assessment
  - velocity_analysis
  - delivery_acceleration
  - additional_data_needs
- Use ISO 8601 format for all dates (YYYY-MM-DD)
- Round numeric values (e.g., data_coverage) to one decimal place
- Output valid JSON only with no extra text or unescaped newlines
"""

# Create prompt template for Git initiatives
git_prompt_template = PromptTemplate(
    template=git_system_template,
    input_variables=["summary_data", "initiative", "current_date"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=False)
    },
)

# Initialize LLM
llm = get_llm(max_tokens=10000).with_structured_output(InitiativeEstimate) | to_dict_parser
git_method04_chain = git_prompt_template | llm

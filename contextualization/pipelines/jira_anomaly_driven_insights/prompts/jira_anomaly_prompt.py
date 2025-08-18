from typing import Annotated

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.models.anomaly_insights import ConfidenceLevel, InsightCategory
from contextualization.pipelines.common.anomalies_postprocessing import prompt_template_anomalies_postprocessing
from contextualization.tags import get_tags_prompt
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser
from contextualization.utils.pydantic_validators import category_validator

# Jira Data Analysis Prompt
system_template_jira_analysis = """

### **TAG DEFINITIONS**
{tag_definitions}

<task>
Analyze the provided Jira ticket data to identify significant anomalies and risks in project management and engineering workflows, with special attention to ticket category or stage category patterns and distributions. Follow the given framework principles for pattern identification and reporting.
</task>

You are tasked with analyzing Jira data to identify meaningful anomalies that reflect significant deviations in project management and engineering workflows. Focus exclusively on system and team-level patterns rather than individual performance metrics, adhering to the Feldman Doctrine.

### **Category Definitions:**
[ANOMALY_CATEGORY_DEFINITIONS]

### Anomaly Definition
Anomalies represent significant deviations from expected patterns. It can be positive or negative. 
Highlight both positive and negative anomalies, don't limit analysis to a few examples of each category.

### Category-Aware Analysis Framework:
The Jira data includes ticket categories such as:
- Bug: System failures, defects, and error conditions
- Story: Feature development and user requirements
- Incident: Production issues and service disruptions  
- Request: Access requests and system configuration changes
- Manual Testing: User acceptance and manual verification tasks
- Automated Testing: Test automation and CI/CD pipeline tasks
- Other: Documentation, maintenance, and miscellaneous tasks

### Category-Specific Anomaly Patterns to Identify:

#### Category Distribution & Quality Anomalies:
- Unusual proportions of specific categories or sudden shifts in distribution over time
- Story tickets lacking proper acceptance criteria, Incident tickets with inadequate root cause analysis

#### Cross-Category Workflow & Resource Anomalies:
- Bug tickets taking significantly longer to resolve than Story tickets
- Incident tickets not prioritized appropriately, Testing tickets created without corresponding Story/Bug tickets
- Teams spending disproportionate time on Bug fixes vs Story development
- Request handling showing bottlenecks, Incident response showing resource strain

### Core Analysis Focus Areas:
1. **Activity Distribution Anomalies**: Unusual distribution of work types, development focus shifts, category imbalances
2. **Temporal Pattern Anomalies**: Unexpected cadence variations, timeline deviations by category
3. **Resource Allocation Anomalies**: Shifts in effort distribution across categories
4. **Quality Signal Anomalies**: Changes in implementation approaches, test coverage
5. **Process Adherence Anomalies**: Workflow pattern changes, procedural deviations by category
6. **Business Alignment Anomalies**: Strategy execution patterns, priority alignment issues across categories
7. **Stage Distribution Anomalies**: Unusual patterns in ticket stage progression and distribution

### Specific Jira Patterns to Identify:
- Clusters of related tickets within the same category with similar issues
- Timeline anomalies (creation to resolution time) varying significantly by category
- Unusual priority distribution or shifts within specific categories
- Component-specific patterns affecting certain categories more than others
- Anomalies in ticket descriptions or metadata quality varying by category
- Unusual status transitions or workflow patterns specific to certain categories
- Assignment patterns and workload distribution (team-level only) across different categories
- **Stage-specific patterns**: Unusual distributions across "Underway", "Ready for Work" stages
- **Stage stagnation patterns**: Tickets stuck in particular stages longer than expected
- **Stage bypass patterns**: Tickets skipping expected stage progressions
- **Stage clustering issues**: Disproportionate accumulation in specific stages

### Stage Analysis Requirements:
All anomalies and risks must include stage context where relevant:
- Identify which stage(s) the pattern occurs in
- Note unusual stage distributions
- Highlight stage-specific bottlenecks or flow issues
- Report on stage progression patterns that deviate from expected workflows
- Focus on stage-related process adherence issues


### Category-Aware Insight Examples:
- "Incident tickets comprised 60% of total volume this sprint compared to the typical 15%, suggesting systemic stability issues"
- "Testing category tickets were consistently resolved 3x faster than Bug tickets, potentially indicating inadequate test depth"

### Guiding Principles:
- **Feldman Doctrine Adherence**: Teams, not individuals; patterns, not performance
- **Human Dignity and Respect**: Describe systems, not blame people
- **Growth-Oriented Purpose**: Insights for improvement, never for evaluation
- **Evidence-Based Objectivity**: Show your work; separate facts from interpretation
- **System-Focused Perspective**: Systems create patterns; change systems to change outcomes
- **Proportional Response Framework**: Match your tone to the actual impact
- **Business Impact Transparency**: Connect technical findings to business outcomes
- **Continuous Improvement Culture**: Celebrate progress and encourage experimentation
- **Category Context Awareness**: Always consider category context when analyzing patterns

### Format Requirements:
- Insights must be 2-4 sentences maximum, including all necessary detail and context
- Write in past tense for observed patterns
- Business impact statement required in all insights
- Pattern evolution framing included where relevant
- Use pattern-first structure consistently
- Include explicit comparison basis in each insight, especially cross-category comparisons
- Focus exclusively on system and team-level patterns, never on individuals
- Apply bidirectional neutrality to treat positive and negative patterns equally
- When relevant, explicitly mention the category or categories involved in the anomaly
- Specify which stage(s) are involved in the pattern if relevant
- IMPORTANT: Do NOT include category tags like "[Quality Impact]" in the insight field - the category should only be specified in the separate "category" field

### Significance Score Criteria:
- **Level 1-6: "Team Member's Attention"**
  - Relevant to individual contributors or small sub-teams
  - Represents minor deviations (0-1σ) from baseline expectations
  - Limited to specific functions, features, or isolated components
  - Provides tactical information for day-to-day decision-making
  - *Not shown in executive views*

- **Level 7: "Team Lead's Attention"**
  - Relevant to daily operations of specific teams
  - Appropriate for team lead awareness
  - Represents moderate deviation (1-1.5σ) from baseline
  - Affects specific codebases or work patterns
  - Provides useful context for team-level decisions
  - *Shown in secondary view*

- **Level 8: "Director/Manager's Attention"**
  - Notable impact on specific product areas or technical components
  - Warrants director or senior manager attention
  - Represents significant deviation (1.5-2σ) from baseline
  - Affects specific teams or product components
  - Provides important signals for technical decision-making
  - *Shown in secondary view*

- **Level 9: "CTO/CPO's Attention"**
  - Substantial impact on technical operations or delivery timelines
  - Requires attention from senior engineering or product leadership
  - Represents major deviation (2-3σ) from expected patterns
  - Affects important systems or significant portion of development activity
  - Creates meaningful technical risk or opportunity
  - *Shown in primary view*

- **Level 10: "CEO's Attention"**
  - Direct, measurable impact on business outcomes or major customer commitments
  - Requires organizational priority shift or immediate resource allocation
  - Represents exceptional deviation (>3σ) from normal operations
  - Affects multiple parts of the organization or critical system components
  - Creates material risk to revenue, security, or customer satisfaction
  - *Shown in primary view*

### Confidence Level Guidelines:
- **High Confidence**: Strong statistical significance (p<0.01), large sample, consistent pattern
- **Medium Confidence**: Moderate significance (p<0.05), adequate sample, some variability
- **Low Confidence**: Borderline significance, limited data, or high variability

### Text Construction Principles:
- **Pattern-First Clarity**: Begin with a clear statement of the observed pattern
- **Evidence-Based Specificity**: Include specific, quantifiable evidence
- **System-Focus Language**: Focus on systems, processes, and technical components rather than people
- **Neutral Observation Tone**: Maintain objective, observation-based tone
- **Context Inclusion**: Provide relevant context for proper interpretation, including category context
- **Business Relevance Connection**: Relate technical patterns to business outcomes
- **Pattern Evolution Framing**: Describe how patterns have changed over time
- **Proportional Emphasis**: Match language intensity to actual significance
- **Bidirectional Neutrality**: Treat positive and negative anomalies with equal analytical rigor
- **Technical Precision**: Use accurate technical terminology and precise descriptions
- **Category Integration**: Naturally incorporate category information when it adds meaningful context
- **Stage Integration**: Include stage context in pattern descriptions where relevant

### Category Analysis Priority:
When analyzing the data, pay special attention to:
1. **Cross-category documentation** - Categories consistently showing lower quality documentation
2. **Category volume imbalances** - Unusual spikes or drops in specific categories
3. **Category-specific timeline patterns** - Categories consistently taking longer to resolve
4. **Category workflow deviations** - Categories bypassing normal processes
5. **Category priority misalignments** - Categories that may be under or over-prioritized

Highlight both positive and negative anomalies.
Important: For analysis of an anomaly or risk give more weightage to columns like 'summary', 'description', and 'category' over other columns. The category field provides crucial context for understanding the nature and expected patterns of each ticket.

### Analysis Instructions:
1. ALWAYS compare patterns across different ticket categories
2. Quantify differences between categories whenever possible
3. Identify which categories are outliers in any given pattern
4. Look for category-specific workflow or quality issues
5. Frame insights in terms of category comparisons, not just overall patterns

Here is the Jira data to analyze: {jira_data}
"""


class JiraAnomaly(BaseModel):
    category: Annotated[InsightCategory, category_validator] = Field(description="The category of the anomaly")
    title: str = Field(..., description="A concise title summarizing the insight (max 6 words).")
    insight: str = Field(
        description="Pattern-first description of the anomaly following framework guidelines. [FORMAT_AS_BULLET_POINTS]"
    )
    evidence: str = Field(
        description="Specific evidence from the Jira data supporting this anomaly. [FORMAT_AS_BULLET_POINTS]"
    )
    significance_score: int = Field(description="Significance score from 1-10 based on framework guidelines")
    confidence_level: ConfidenceLevel = Field(description="Level of confidence in the anomaly")


class JiraAnomalyReport(BaseModelThatRemovesTags):
    anomaly_insights: list[JiraAnomaly] = Field(
        description="List of significant positive anomalies", default_factory=list
    )


prompt_template_jira = PromptTemplate(
    template=system_template_jira_analysis,
    input_variables=["jira_data"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=True)
    },
)

llm = get_llm(max_tokens=5_000).with_structured_output(JiraAnomalyReport) | to_dict_parser
jira_anomaly_analysis_chain = prompt_template_jira | llm


system_template_summary_jira_analysis = """

### **TAG DEFINITIONS**
{tag_definitions}

<task>
Analyze multiple batches of Jira anomaly insights and risk insights to produce a consolidated, high-impact summary that highlights the most significant patterns while eliminating redundancy.
</task>
You are a data pattern consolidation system tasked with synthesizing Jira project anomalies and risks across multiple analysis batches. Your goal is to identify the most significant patterns, eliminate redundancies, and produce a concise, impactful summary that maintains the analytical rigor of the original insights.

### **Category Definitions:**
[ANOMALY_CATEGORY_DEFINITIONS]

Anomaly and Risk Synthesis Guidelines
## Consolidation Principles:

Pattern Recognition: Identify similar anomalies or risks across batches and consolidate them into unified insights.
Evidence Aggregation: Combine supporting evidence from multiple batches for stronger consolidated insights.
Significance Prioritization: Prioritize higher significance score items (8-10) over lower ones when similar.
Confidence Weighting: Give preference to "High Confidence" insights over "Medium" or "Low" when similar.
Evidence Strength Assessment: Evaluate the quality and quantity of evidence when deciding which insights to retain.
Category Balance: Ensure representation across all relevant categories [ANOMALY_CATEGORIES].
Language Precision: Maintain the technical precision and clarity of the original insights.
Feldman Doctrine Adherence: Focus exclusively on team and system-level patterns, never individuals.

## Synthesis Methodology:

Group similar insights by theme and category across batches
Combine evidence that supports related observations
Craft consolidated insights that capture the breadth of the pattern
Adjust significance scores based on pattern prevalence and impact
Assign the highest confidence level that is justified by the combined evidence
Maintain the pattern-first structure consistently in all consolidated insights
Ensure each insight remains within 2-4 sentences despite consolidation

## Output Filtering Criteria:

Eliminate redundant insights that describe the same fundamental pattern
Remove lower-significance insights (score of 7) when similar higher-significance insights exist
Prioritize insights with concrete, quantifiable evidence over general observations
Maintain a balanced representation across anomaly categories
Focus on system-level patterns with the highest business impact

Anomaly insights are 'positive' deviations.
Risk insights are 'negative' deviations.
Here is the Jira anomaly and risks json data to analyze: {jira_data}
"""


class JiraAnomalySummary(BaseModel):
    category: Annotated[InsightCategory, category_validator] = Field(description="The category of the anomaly")
    title: str = Field(..., description="A concise title summarizing the insight (max 6 words).")
    insight: str = Field(
        description="Pattern-first description of the anomaly following framework guidelines. [FORMAT_AS_BULLET_POINTS]"
    )
    evidence: str = Field(
        description="Specific evidence from the Jira data supporting this anomaly. [FORMAT_AS_BULLET_POINTS]"
    )
    significance_score: int = Field(description="Significance score from 1-10 based on framework guidelines")
    confidence_level: ConfidenceLevel = Field(description="Level of confidence in the insight")

    """
    The regex for the field "source" has been implemented by studying the answers at https://stackoverflow.com/questions/19322669/regular-expression-for-a-jira-identifier
    """
    source: list[str] = Field(
        description=(
            "Extract all valid, standalone JIRA ticket IDs from the 'evidence' field. "
            "A valid JIRA ID matches the pattern [A-Z]+-[0-9]+ (e.g., 'PROJ-123'). "
            "Do not include IDs embedded within other words or patterns (e.g., exclude 'abcDEF-33'). "
            "Ensure the ID is not immediately preceded by another letter-hyphen pattern. "
            "Use regex: (?<![A-Za-z]{1,10}-)[A-Z]+-\\d+"
        ),
        examples=[["BF-18", "X-88", "ABCDEFGHIJKL-999", "ABC-1"]],
    )


class JiraAnomalyReportSummary(BaseModelThatRemovesTags):
    anomaly_insights: list[JiraAnomalySummary] = Field(
        description="List of significant positive anomalies", default_factory=list
    )


summary_prompt_template_jira = PromptTemplate(
    template=system_template_summary_jira_analysis,
    input_variables=["jira_data"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=True)
    },
)

llm = get_llm(max_tokens=5_000).with_structured_output(JiraAnomalyReportSummary) | to_dict_parser
jira_anomaly_analysis_summary_chain = summary_prompt_template_jira | llm


# Define Pydantic models for skip-a-meeting output
class SkipMeetingMessage(BaseModel):
    audience: str = Field(description="Who (person/team) should receive this message")
    message_for_audience: str = Field(
        description="Specific message tailored to the audience. [FORMAT_AS_BULLET_POINTS]"
    )


class JiraSkipMeetingInsight(BaseModel):
    resolution: str = Field(description="Actionable plan to communicate this insight without a meeting")
    messages: list[SkipMeetingMessage] = Field(description="List of messages for different audiences")


class JiraSkipMeetingReport(BaseModelThatRemovesTags):
    skip_a_meeting_insight: JiraSkipMeetingInsight | None = Field(
        default=None, description="actions to skip a meeting based on insight"
    )


# System template for skip-a-meeting analysis
system_template_skip_meeting = """

### **TAG DEFINITIONS**
{tag_definitions}

You are an expert in analyzing critical anomalies in software development and project management workflows. For context, these anomalies are extracted by analyzing Jira tickets, workflows, and project data. The analysis considers ticket completeness, technical details, and process impacts to identify risks and opportunities.

### **Category Definitions:**
[ANOMALY_CATEGORY_DEFINITIONS]

Given the following anomaly details:
### Input Format:
A dictionary where the keys are constant and the values explain the keys in this example:
    "repo": "Name of the project",
    "category": "Category of the anomaly (e.g., [ANOMALY_CATEGORIES]",
    "insight": "Insights about the anomaly, what the anomaly is and its description",
    "evidence": "Where the anomaly is present or where in the tickets/workflow it can be observed",
    "significance_score": "A score based on significance of the anomaly",
    "confidence_level": "A confidence level based on significance score (i.e., High, Medium, Low)"
# Significance Score Scale Information:
    Level 10: CEO's Attention (Executive leadership)
    Level 9: Product Managers' Attention (Product leadership)
    Level 8: Development Team Leads' Attention (Technical team leaders)
    Level 7: Developers' Attention (Individual contributors)
    Levels 1-6: Development Team's Attention (Team members, always include Developers)
### Task:
- Given the following insight, generate a SkipAMeeting suggestion. This should include:
- How the issue can be resolved asynchronously (e.g., updating tickets, sharing docs in Slack).
- Dynamic audience determination: Based on the significance score, determine the sender and multiple relevant audience types to receive communications.
- Multiple audience-specific messages, tailored to specific stakeholder groups.
    Each message should:
        - Frame the issue as an opportunity for collaborative problem-solving in short
        - Present thought-provoking questions that prompt specific, substantive responses
        - Suggest relevant context that enables asynchronous discussion
{jira_anomaly}

Instructions:
- Maintain tone between -2 and +2 on a -10 to +10 emotional scale.
- Use moderate language: Maximum positive: "pleased" (never "excited," "thrilled"); Maximum negative: "unfortunately" (never "alarming," "critical").
- Avoid first-person references ("I," "we," "our").
- Use objective, third-person descriptions focused on data and events rather than opinions.
- Attribute observations to systems/data rather than people.
- Convey urgency through impact statements and precise metrics rather than emotional language.
- Replace imperative commands with options (e.g., "Options include..." instead of "Please implement...").
- Be clear and direct—avoid unnecessary details.
- Ensure the message is actionable so that teams can quickly address the issue.
- Use the insight details to craft a relevant and effective response.
- Provide specific steps or solutions, not vague suggestions.
- Based on the significance score, determine the appropriate sender and audience, tailoring messages accordingly.

Instructions for "resolution":
    For negative anomalies:
        - Provide 2-3 specific, actionable steps to address the issue
        - Include potential technical approaches with their respective trade-offs
        - Reference relevant documentation, best practices, or similar past incidents if applicable
        - Suggest testing or validation methods to confirm resolution
        - Indicate priority level based on significance score and business impact
    For positive anomalies:
        - Summarize the beneficial aspects and potential value to the organization
        - Suggest ways to leverage or expand upon the positive development
        - Identify opportunities for knowledge sharing or standardization
        - For higher significance scores (7-10), include potential strategic implications
        - For lower significance scores (1-6), focus on tactical implementation details
    Additional considerations when needed:
        - Scale technical complexity according to the target audience
        - Include estimated effort/time investment when relevant
        - Suggest appropriate documentation updates or knowledge sharing actions
        - Provide clear success criteria that indicate when the matter is resolved
        - Number the steps in the resolution for clarity
        - Always add a new line after each step

Instructions for "messages":
- Generate 2-3 specific, non-obvious questions that require thoughtful responses.
- Provide enough context for informed discussion without prescribing complete solutions.
- Include clear indicators of what type of feedback would be most valuable.
- Ensure questions are specific to the anomaly details and cannot be answered with yes/no.
- Structure messages to invite ongoing conversation rather than close discussion.
- Adapt message complexity and technical detail based on the audience determined by the significance score.
- For positive anomalies, frame questions around optimization and strategic leverage.
- For negative anomalies, frame questions around risk mitigation and technical solutions.
- Do not include names of developer or team members.
- **IMPORTANT** Do not include names of developer or team members.
"""

# Initialize skip meeting parser
prompt_template_skip_meeting = PromptTemplate(
    template=system_template_skip_meeting,
    input_variables=["jira_anomaly"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=True)
    },
)


# Initialize the model with the proper configuration
llm = get_llm(max_tokens=10000).with_structured_output(JiraSkipMeetingReport) | to_dict_parser
skip_meeting_analysis_chain = prompt_template_skip_meeting | llm


class PostprocessedInsight(JiraAnomaly):
    need_to_be_removed: bool = Field(default=False, description="If True, the insight should be removed")


llm_insights_postprocessing = get_llm(max_tokens=5000).with_structured_output(PostprocessedInsight) | to_dict_parser
llm_postprocessing_chain = prompt_template_anomalies_postprocessing | llm_insights_postprocessing

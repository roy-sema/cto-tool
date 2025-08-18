from typing import Annotated

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.models.anomaly_insights import ConfidenceLevel, InsightCategory
from contextualization.pipelines.common.anomalies_postprocessing import prompt_template_anomalies_postprocessing
from contextualization.tags import get_tags_prompt
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser
from contextualization.utils.pydantic_validators import category_validator, parse_json_string_validator


class FileInfo(BaseModel):
    file_name: str
    branch_name: str
    commit_id: str


class CombinedInsightSchema(BaseModel):
    category: Annotated[InsightCategory, category_validator] = Field(description="The category of the insight")
    title: str = Field(..., description="A concise title summarizing the insight (max 6 words).")
    description: str = Field(description="Description about the insights. [FORMAT_AS_BULLET_POINTS]")
    evidence: str = Field(description="Evidence about the insights. [FORMAT_AS_BULLET_POINTS]")
    significance_score: float = Field(description="significance_score for each insight to indicate significance level")
    confidence_level: ConfidenceLevel = Field(
        description="confidence_level (High/Medium/Low) based on the strength of evidence"
    )
    sources: list[str] = Field(description="List of accurate commit ids from provided input data for observed anomaly")
    files: list[FileInfo]


class ExecutiveSummaryCTOAnomalyInsights(BaseModelThatRemovesTags):
    anomaly_insights: Annotated[list[CombinedInsightSchema], parse_json_string_validator] = Field(
        default_factory=list,
        description="A list of dictionaries about a highlight variance from previous practice.",
    )


class ExecutiveSummaryCTORiskInsights(BaseModel):
    risk_insights: Annotated[list[CombinedInsightSchema], parse_json_string_validator] = Field(
        default_factory=list,
        description="A list of dictionaries about a negative variance from recommended practice.",
    )


prompt_base = """

### **TAG DEFINITIONS**
{tag_definitions}

Generate a simplified executive summary for the CTO focusing on development patterns and risk variances.
Each insight MUST include both a pattern description, specific pattern evidence, and a confidence score.

IMPORTANT: Process all formatting tags according to their instructions, but DO NOT include the tag text itself in the output.
For example, when you see [FORMAT_AS_BULLET_POINTS], format the content as bullet points but remove the tag from the response.


Risk Variances (Pattern Areas for Attention)
- Categorize the pattern variances into [ANOMALY_CATEGORIES]
- Include pattern emergence related to velocity improvements, quality enhancements, architectural evolution, and system integrations
- Identify emergent patterns related to systemic issues, delivery bottlenecks, technical debt accumulation, or architectural drift
- Ensure each risk variance represents a significant pattern worthy of executive attention
- Assign a significance_score (1-10) based on the significance scale to prioritize findings
- Assign the appropriate confidence_level based on the confidence levels
- Include a list of file metadata where the patterns has been observed. Files is a list of dict with keys - "file_name", "branch_name", and "commit_id" and their respective values. Example of the files list is as follows:
     "files":[
        {{
            "commit_id" : "10b044b3",
            "file_name": "hotfix_1.py",
            "branch_name": "feature/release-june-15-2025"
        }},
        {{
            "commit_id" : "10c084z3",
            "file_name": "url_contain.py",
            "branch_name": "origin/main"
        }},
     ]. 
     NEVER generate, infer, or fabricate the list of files. - only reference commit_id, file_name, and branch_name explicitly present in the provided data.
     Infer the value of the key file_name strictly as the full directory or relative path, including the file name and its extension (e.g., .txt, .csv, .py). Return the path exactly as it appears in the source data—do not guess, modify, or generate it.

### **Category Definitions:**
[ANOMALY_CATEGORY_DEFINITIONS]

### **Significance Scale for significance_score:**
Levels 1-6: "Team Member's Attention"
    - Relevant to individual contributors or small sub-teams
    - Represents minor deviations (0-1σ) from baseline expectations
    - Limited to specific functions, features, or isolated components
    - Provides tactical information for day-to-day decision-making
Level 7: "Team Lead's Attention"
    - Relevant to daily operations of specific teams
    - Appropriate for team lead awareness
    - Represents moderate deviation (1-1.5σ) from baseline
    - Affects specific codebases or work patterns
    - Provides useful context for team-level decisions
Level 8: "Director/Manager's Attention"
    - Notable impact on specific product areas or technical components
    - Warrants director or senior manager attention
    - Represents significant deviation (such as 1.5-2σ) from baseline
    - Affects specific teams or product components
    - Provides important signals for technical decision-making
Level 9: "CTO/CPO's Attention"
    - Substantial impact on technical operations or delivery timelines
    - Requires attention from senior engineering or product leadership
    - Represents major deviation (such as 2-3σ) from expected patterns
    - Affects important systems or significant portion of development activity
    - Creates meaningful technical risk or opportunity
Level 10: "CEO's Attention"
    - Direct, measurable impact on business outcomes or major customer commitments
    - Requires organizational priority shift or immediate resource allocation
    - Represents significant deviation (such as >3σ but we may not calculate it as such) from normal operations
    - Affects multiple parts of the organization or critical system components
    - Creates material risk to revenue, security, or customer satisfaction
#### Scoring incorporates:
* Statistical deviation magnitude
* Business impact assessment
* Relation to critical path or strategic priorities
* Scope of impact (component, service, system-wide)

### **Confidence Levels:**
- **High Confidence**: Strong statistical significance (p<0.01), large sample, consistent pattern
- **Medium Confidence**: Moderate significance (p<0.05), adequate sample, some variability
- **Low Confidence**: Borderline significance, limited data, or high variability

For all insights:
- ANALYZE BOTH git tree and git diff inputs comprehensively to understand the full pattern context
- Identify recurring patterns and trends rather than focusing on individual implementations
- Cross-reference pattern information between both data sources to ensure pattern accuracy
- Prioritize insights that reveal strategic pattern evolution or significant pattern impacts
- Focus on system-level patterns that demonstrate understanding of the project's technical direction and business impact
- Extract concrete references from the data like "TICKET-123 for AWS Bedrock integration" or "pull request #11 for performance optimization" ONLY if provided
- Do not use placeholder text for pattern evidences
- Maintain a balanced perspective but emphasize positive pattern highlights over negative pattern variances
- Keep pattern insights concise and focused rather than providing long explanations
- Always use past tense for all pattern descriptions and evidences

##Important instructions:
- **Return only the JSON result as output with no introductory text("Here's the json") or explanation**
- If input is missing, include this information within the JSON structure itself
- Ensure the output is valid, properly formatted JSON with no surrounding text
- NEVER generate, infer, or fabricate commit IDs - only reference IDs explicitly present in the provided data.

Here's the input for analysis:
git tree analysis content: {git_tree_analysis_content}
git diff analysis json: {git_diff_analysis_content}
"""

prompt_template_anomaly_insights = PromptTemplate(
    template=prompt_base,
    input_variables=["git_tree_analysis_content", "git_diff_analysis_content"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=True),
    },
)

llm_summary = get_llm(max_tokens=10_000).with_structured_output(ExecutiveSummaryCTOAnomalyInsights) | to_dict_parser
cto_summary_chain_anomaly_insights = prompt_template_anomaly_insights | llm_summary


class PostprocessedInsight(CombinedInsightSchema):
    need_to_be_removed: bool = Field(default=False, description="If True, the insight should be removed")


llm_insights_postprocessing = get_llm(max_tokens=5000).with_structured_output(PostprocessedInsight) | to_dict_parser
llm_postprocessing_chain = prompt_template_anomalies_postprocessing | llm_insights_postprocessing

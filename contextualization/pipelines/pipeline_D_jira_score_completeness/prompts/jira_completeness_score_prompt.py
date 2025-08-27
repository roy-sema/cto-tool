from langchain.prompts import PromptTemplate
from pydantic import Field

from contextualization.conf.get_llm import get_llm
from contextualization.tags import get_tags_prompt
from contextualization.utils.output_parser import BaseModelThatRemovesTags

system_template = """

### **TAG DEFINITIONS**
{tag_definitions}

You are an expert in analyzing JIRA tickets with deep experience in agile development processes, requirement engineering, and quality assurance. Your specialized role is to evaluate the completeness of JIRA tickets by examining their structure, content, and adherence to best practices. Your analysis helps development teams identify gaps in requirements before work begins, significantly reducing rework and improving delivery predictability.

## Scoring Methodology

### 1. Acceptance Criteria Clarity (25 points)
- **Excellent (21-25)**: Comprehensive, specific, testable criteria covering all user scenarios
- **Good (16-20)**: Clear criteria with minor gaps in specificity or edge cases
- **Adequate (11-15)**: Basic criteria present but lacking detail or measurability
- **Concerning (6-10)**: Vague criteria with significant gaps
- **Initial (0-5)**: Minimal or missing acceptance criteria

### 2. Requirements Detail (30 points)
- **Excellent (25-30)**: Thorough description with clear user story, context, and business value
- **Good (19-24)**: Solid description with good context but minor details missing
- **Adequate (13-18)**: Basic description that communicates core functionality
- **Concerning (7-12)**: Vague description with significant details missing
- **Initial (0-6)**: Minimal or confusing description

### 3. Attachments & References (15 points)
- **Excellent (12-15)**: All necessary supporting materials present based on ticket complexity and type
- **Good (9-11)**: Most necessary supporting materials present with minor gaps
- **Adequate (6-8)**: Some supporting materials present, but missing some that would be helpful
- **Concerning (3-5)**: Missing critical supporting materials that are necessary for this work
- **Initial (0-2)**: No supporting materials despite clear necessity

*Note: If a ticket's complexity doesn't require attachments, award full points. If attachments are present but unnecessary, also award full points. Deduct points only for missing necessary attachments.*

### 4. Dependencies Identification (10 points)
- **Excellent (8-10)**: All dependencies and relationships clearly identified
- **Good (6-7)**: Major dependencies identified with minor omissions
- **Adequate (4-5)**: Basic dependencies identified
- **Concerning (2-3)**: Major dependencies missing
- **Initial (0-1)**: No dependencies identified when they clearly exist

### 5. Technical Specification (10 points)
- **Excellent (8-10)**: Clear technical implementation details appropriate for ticket complexity
- **Good (6-7)**: Good technical information with minor gaps
- **Adequate (4-5)**: Basic technical information
- **Concerning (2-3)**: Insufficient technical details where needed
- **Initial (0-1)**: No technical details where clearly needed

### 6. Edge Case Coverage (10 points)
- **Excellent (8-10)**: Comprehensive coverage of exception scenarios where needed
- **Good (6-7)**: Most relevant edge cases covered with minor omissions
- **Adequate (4-5)**: Basic edge cases considered where needed
- **Concerning (2-3)**: Critical edge cases missing
- **Initial (0-1)**: No edge cases considered despite clear need

*Note: For simple tickets where edge cases are not relevant, award full points. Only deduct points when edge cases are missing but clearly needed based on ticket complexity and purpose.*

## Overall Scoring Scale
* **90-100**: Excellent - Comprehensive requirements, minimal clarification needed
* **75-89**: Good - Clear requirements with minor gaps, low risk
* **60-74**: Adequate - Basic requirements present, some clarification likely needed
* **40-59**: Concerning - Significant gaps requiring substantial clarification
* **0-39**: Initial - Fundamental requirements missing, high risk of delays and rework

Input jira ticket data:
{jira_ticket_row}

## Output Format
1. An overall completeness score (1-100)
2. A detailed evaluation of each scoring factor (scores and justifications)
3. A short description of the ticket details (with issue key), including the reason for the score.

Follow the scoring instructions and score only based on the instructions. Make sure the count is accurately calculated and validated. Do not award points for missing necessary information, and do not hallucinate content not present in the ticket.
Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON. If it isn't, correct it and return valid JSON only.
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class JiraScore(BaseModelThatRemovesTags):
    jira_completeness_score: int = Field(description="Jira completeness score according to the data")
    evaluation_jira_completeness_score: str = Field(
        description="Evaluation of score for each category and there justification"
    )
    explanation_jira_completeness_score: str = Field(
        description="Description of jira completeness score. [FORMAT_AS_BULLET_POINTS]"
    )


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["jira_ticket_row"],
    partial_variables={
        "tag_definitions": get_tags_prompt(format_as_bullet_points=True, include_anomaly_categories=False)
    },
)

llm = get_llm(max_tokens=5000).with_structured_output(JiraScore)
jira_completeness_score_chain = prompt_template | llm

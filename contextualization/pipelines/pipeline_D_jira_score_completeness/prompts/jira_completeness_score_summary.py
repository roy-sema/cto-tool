from langchain.prompts import PromptTemplate
from pydantic.v1 import BaseModel, Field  # No idea why it doesn't work on V2

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import to_dict_parser

# NOTE: Uncommented the code to reuse the category_summary_chain
# Category summary prompt (for excellent, average, and initial categories)
category_system_template = """You are tasked with generating a detailed summary of a specific quality category of Jira tickets.
You will receive JSON data containing information about Jira tickets that fall into one quality category (excellent, average, or initial).

Input JSON file: <json>{jira_tickets_data}</json>

OUTPUT Instructions: Generate a focused quality assessment for this specific category that:
1. Identifies key patterns in completeness and quality within this group of tickets
2. Provides 2-3 specific examples of tickets in this category with brief details
3. Offers targeted recommendations to improve tickets in this category

Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON.
Note: Do not include any boilerplate context like "here is the json" before the actual json output.
"""


class ExampleJiraTicket(BaseModel):
    ticket: str = Field(description="Jira ticket ID (e.g., 'PROJ-123')")
    score: int = Field(description="Score of the ticket. Between 0 and 100, where 100 is the best score.")
    explanation: str = Field(description="Explanation related a particular ticket")


class CategorySummary(BaseModel):
    patterns: str = Field(description="Common patterns or characteristics of tickets in this category")
    examples: list[ExampleJiraTicket] = Field(
        description="2-3 specific examples of tickets in this category with brief details"
    )
    recommendations: list[str] = Field(description="Specific recommendations to improve tickets in this category")


category_summary_prompt = PromptTemplate(
    template=category_system_template,
    input_variables=["jira_tickets_data"],
)

llm = get_llm(max_tokens=4000).with_structured_output(CategorySummary) | to_dict_parser
category_summary_chain = category_summary_prompt | llm

# Final consolidated summary prompt
final_system_template = """You are tasked with generating a comprehensive executive summary of Jira ticket quality across the entire project.
You will receive JSON data containing categorized information about Jira tickets, including category counts and individual category summaries.

Input JSON file: <json>{jira_tickets_data}</json>

OUTPUT Instructions: Generate a consolidated quality assessment that:
1. States the total number of tickets analyzed and their distribution across quality categories
2. Synthesizes the key findings from each quality category (excellent, average, initial)
3. Provides an overall assessment of the project's Jira ticket quality
4. Offers prioritized recommendations to improve overall ticket quality

Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON.
Note: Do not include any boilerplate context like "here is the json" before the actual json output.
"""


class FinalSummary(BaseModel):
    overview: str = Field(description="Overview of the total tickets and their distribution across quality categories")
    key_findings: list[str] = Field(description="Key findings synthesized from all quality categories")
    overall_assessment: str = Field(description="Overall assessment of the project's Jira ticket quality")
    prioritized_recommendations: list[str] = Field(
        description="Prioritized recommendations to improve overall ticket quality"
    )


final_summary_prompt = PromptTemplate(
    template=final_system_template,
    input_variables=["jira_tickets_data"],
)

# Configure LLM with sufficient tokens for complex analysis
llm = get_llm(max_tokens=4000).with_structured_output(FinalSummary) | to_dict_parser
final_summary_chain = final_summary_prompt | llm

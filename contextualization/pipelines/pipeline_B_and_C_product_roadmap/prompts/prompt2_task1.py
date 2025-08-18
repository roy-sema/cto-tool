from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

system_template = """You are an expert in analyzing summaries of code changes and commit histories from GitHub repositories. Given the summary data from code pushes, your task is to extract specific, detailed insights by identifying major development activities and the exact names or descriptions of features or work completed. Specifically, you are able to:
1. Detect important development works and name them explicitly, such as specific features (e.g., "User Profile Page Redesign," "Payment Gateway Integration"), bug fixes (e.g., "Fixed session timeout error"), refactoring efforts (e.g., "Modularized API structure"), or performance optimizations (e.g., "Reduced API response time by 20%").
2. Identify which specific areas of the product (e.g., "Checkout Flow in the UI," "Database schema for Orders Table," "OAuth-based Authentication") have undergone significant changes and provide context for where these changes occurred. Avoid generic terms like "UI development" or "backend development" unless the exact area is unavailable in the summary.
3. Assess the impact of these changes on the product, providing clear, specific outcomes such as "enhanced payment processing speed," "reduced memory usage by 15%," "improved user authentication security," or "eliminated redundant code, lowering technical debt.":
4. Your output should prioritise details and avoid vague terms like 'feature development' or 'backend updates' unless the exact details are missing from the provided data. If the summaries include feature or component names, ensure they are reflected in your analysis.
{chat_prompt}
Given this summary data from a series of commits, please analyze and provide the most important information, focusing on:
1. What specific major work has been done.
2. The names or descriptions of the features, bugs, or refactored components.
3. The specific areas of the product that were impacted.
4. The impact of the changes on the product.
Data Provided:
<csv> {csv_schema} </csv>
<csv-data> {csv} </csv-data>
Task for Analysis:
<task> {task} </task>
"""


class ChangeSummary(BaseModel):
    name: str = Field(description="Name of the area of development/initiative/feature, e.g., UI/Frontend.")
    percentage: float = Field(description="The percentage of changes for this category, e.g., 40.")
    justification: str = Field(
        description="A justification or explanation for why this area had the mentioned percentage of changes."
    )


class DevelopmentSummary(BaseModelThatRemovesTags):
    changes: list[ChangeSummary] = Field(description="List of changes with their name, percentage, and justification.")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["csv_schema", "csv", "task", "chat_prompt"],
)

llm = get_llm(max_tokens=10_000).with_structured_output(DevelopmentSummary) | to_dict_parser
commit_analyser_chain = prompt_template | llm

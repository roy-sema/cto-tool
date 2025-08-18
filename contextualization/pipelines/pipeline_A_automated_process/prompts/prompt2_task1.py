from typing import Annotated

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser
from contextualization.utils.pydantic_validators import parse_json_string_validator

system_template = """
You are a very senior data analyst and project management assistant with deep expertise in using data to help software teams (product management and software engineering) build software that achieves organizational goals. You also have deep personal integrity. You are specialized in reviewing and classifying Git diff summaries from software development activities.
IMPORTANT: Before proceeding with any analysis, verify if CSV data exists between <csv> tags:
- If no data is found between <csv> tags, or if tags are empty, respond ONLY with "data not found" by following the format.
- If the CSV data is empty or contains only whitespace, respond ONLY with "data not found".
- Do not perform any analysis if there is no valid CSV data

You are conducting two tasks. Both tasks analyze the summary of changes made to each file in the Git history and categorize the development work over a specified period.

The first task is to treat the code as if it is about to enter maintenance mode. In maintenance mode, software development activities are kept to a minimum and only to ensure that the product works as expected and functionality bugs are fixed.
You are helping estimate how much lower the engineering activity can be by looking at historical activity levels. For now, we will assume that historical work is representative of future work.
Based on the Git diff data provided:
Categorize the Work:
How much of the work would definitely have been pursued if the codebase was in maintenance mode (category = "Yes")
How much of the work might have been pursued if the codebase was in maintenance mode (category = "Maybe")
How much of the work would definitely not have been pursued if the codebase was in maintenance mode (category = "No")
Allocate the work into one of the following categories: Yes, Maybe, No.
Explain methodology: write up to three bullet points explaining how you put the coding work into Yes/ Maybe/ No. categories.
Quantify the Effort: Break down the total work by assigning percentages based on csv data to the different primary categories (Yes/Maybe/No), ensuring the total adds up to 100%.

It may be helpful to first allocate the work into the following categories based on csv data.
Whether or not you need to allocate the work into categories to complete the first task, you will need to do so for the second task.

In the second task, you are helping an software development team sort its recent development activity so it can continue to optimize work allocations.

Critically, in the second analysis task, the software products in question are NOT going to maintenance mode.

Even more critically, as a deeply expert real-world software analyzer, you know there are huge pressures on software development teams to stay focused on features (new features, feature enhancement) rather than bug fixes. Therefore if an activity has some tech debt in it, but also includes significant feature enhancement, you should code it, accurately, as feature enhancement. Remember you are a very high integrity analyst, and it is not acceptable or ethical to fake genuine bug fix / tech debt work and call it feature enhancements.

Tech debt: Refactoring, optimizing code, or upgrading libraries and dependencies.
New feature : Adding new functionalities or capabilities to the software.
Bug fix: Resolving issues, defects, or errors in the existing codebase.
Documentation: Updates or additions to project documentation files (e.g., README, technical documentation).
Feature enhancement: Improving existing functionalities or capabilities to enhance performance, usability, or user experience.
Security: Addressing security vulnerabilities, adding secure coding practices, or enhancing security features.
Testing: Adding new tests, improving existing tests, or modifying test suites (e.g., unit tests, integration tests).
Other: Any other types of work not covered by the above categories (e.g., non-functional changes).
Detailed Rationale: For each category, provide a concise explanation of the changes made, its impact, how it helps to build the product, and the reason for the change (e.g., performance improvement, new functionality, bug resolution).
Description of Changes: Include details such as: The specific module or components impacted by the changes.
The reason for the changes (e.g., fixing a bug, adding a new feature).
Column names: <csv_schema>{csv_schema}</csv_schema>
Data Provided: <csv> {csv} </csv>
Task for Analysis: <task> Categorize and quantify the development work based on the changes made in different files and modules </task>
Ensure that the sum of the work percentages totals 100%.
Provide clear descriptions for why changes were made in each module.
Focus only on the information from the Git diff summaries without adding extraneous context or unrelated details.
Do not include boilerplate text like "here is the json" before the actual response.
Add specific examples, such as repos or folders in the code, specific technologies, and libraries used.
Even when there is a lot of data, pick out 1-2 specific anecdotes to illustrate your points. Mention the specific repository when you provide examples from files in the codebase.
Keep the justification field short. If you do not find examples do not write: "it's not possible to mention specific repositories", or "no specific examples of repositories, folders, technologies, or libraries were provided in the given summary".
Do NOT say that you used summaries to categorize the work. Instead, said that you analyzed code.
"""


class PrimaryCategoryDetails(BaseModel):
    percentage: float = Field(description="percentage as per given csv data else return 0")
    justification: str = Field(
        description="justification as per given csv data. Do not mention specific examples here."
    )
    examples: str = Field(
        description="Examples of code and anecdotes for this category mentioning the repository as per given csv data. Always mention the repository."
    )


# Define the Pydantic class for each category with percentage and justification
class CategoryDetails(BaseModel):
    percentage: float = Field(description="percentage as per given csv data else return 0")
    justification: str = Field(
        description="justification summary as per given csv data. Do not mention specific examples here."
    )
    examples: str = Field(
        description="Examples of code and anecdotes for this category mentioning the repository as per given csv data. Always mention the repository."
    )


class Category(BaseModel):
    tech_debt: CategoryDetails = Field(description="Details for Tech Debt category.")
    new_feature: CategoryDetails = Field(description="Details for New feature category.")
    bug_fix: CategoryDetails = Field(description="Details for Bug Fix category.")
    documentation: CategoryDetails = Field(description="Details for Documentation category.")
    feature_enhancement: CategoryDetails = Field(description="Details for Feature enhancement category.")
    security: CategoryDetails = Field(description="Details for Security category.")
    testing: CategoryDetails = Field(description="Details for Testing category.")
    other: CategoryDetails = Field(description="Details for Other category.")


# Define the Pydantic class for the overall structure with categories and summary
class DevelopmentSummary(BaseModelThatRemovesTags):
    categories: Annotated[Category, parse_json_string_validator] = Field(description="Categories as per given csv data")
    summary: str = Field(description="Summary as per given csv data")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["csv_schema", "csv"],
)

llm = get_llm(max_tokens=10_000).with_structured_output(DevelopmentSummary) | to_dict_parser
commit_analyser_chain = prompt_template | llm

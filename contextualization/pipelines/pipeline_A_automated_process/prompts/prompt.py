from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.tools.llm_tools import get_input_runnable
from contextualization.utils.output_parser import BaseModelThatRemovesTags

system_template = """
You are an expert code reviewer and analysis assistant. Your role is to analyze code changes using `git diff` data. When analyzing, always focus on the following:
1. **Summary of Changes**: Identify specific parts of the code impacted and assess the potential effects of these changes specifying the file, module, component, lines added, modified, or deleted. Summaries the changes how these changes affect the overall product development.
2. **Categorization of Changes**: Classify the changes for a file modified into one of the following categories only: Bug fix, New feature, Tech debt, Feature enhancement, Security, Documentation, Testing, and Other. Do not use any other categories.
3. **Maintenance Relevance**: The product you are analyzing is about to enter maintenance mode. In maintenance mode, software development activities are kept to a minimum and only to ensure that the product works as expected and functionality bugs are fixed. You are helping estimate how much lower the engineering activity can be by looking at historical activity levels. For now, we will assume that historical work is representative of future work.
	Based on the Git diff data provided categorize the Work:
	How much of the work would definitely have been pursued if the codebase were in maintenance mode? (Category = “Yes”)
	How much of the work might have been pursued in maintenance mode? (Category = “Maybe”)
	How much of the work would definitely not have been pursued in maintenance mode? (Category = “No”)
	Allocate the work into one of the following categories: Yes, Maybe, No.
4. **Description of Maintenance Relevance**: Provide the description in points explaining why you put the coding work into Yes/ Maybe/ No categories.
5. **Purpose of Change**: What is the purpose of the change in this commit?
6. **Impact on Product**: Assess how the change affects the overall product.

Git diff data:
<txt> 
{diff} 
</txt> 

Commit title:
<txt> 
{title} 
</txt> 

Commit description:
<txt> 
{description} 
</txt> 

<task> 
Analyze the following `git diff` based on the system-level instructions. Provide the analysis in sections, 
covering the summary, categorization, maintenance relevance, detailed analysis, intent, and whether the changes 
are additive/enhancing or significant. Address potential bugs, code quality, test coverage, and any impact on dependencies.
Add specific examples, such as repos or folders in the code, specific technologies, and libraries used.
Even when there is a lot of data, pick out 1-2 specific anecdotes to illustrate your points. Mention the specific repository when you provide examples from files in the codebase.
Keep the justification field short. If you do not find examples do not write: "it's not possible to mention specific repositories", or "no specific examples of repositories, folders, technologies, or libraries were provided in the given summary".
</task>

Strictly keep the same format everywhere.
Do provide any additional categories other than these Bug fix, New Feature, Tech debt, Security, Documentation, Testing, and Other.
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class DevActivityCategories(BaseModel):
    feature_enhancement: bool = Field(
        description="True if - Feature enhancement: Improving existing functionalities or capabilities to enhance performance, usability, or user experience."
    )
    new_feature: bool = Field(
        description="True if - New feature : Adding new functionalities or capabilities to the software."
    )
    bug_fix: bool = Field(
        description="True if - Bug fix: Resolving issues, defects, or errors in the existing codebase."
    )
    tech_debt: bool = Field(
        description="True if - Tech debt: Refactoring, optimizing code, or upgrading libraries and dependencies."
    )
    security: bool = Field(
        description="True if - Security: Addressing security vulnerabilities, adding secure coding practices, or enhancing security features."
    )
    documentation: bool = Field(
        description="True if - Documentation: Updates or additions to project documentation files (e.g., README, technical documentation)."
    )
    testing: bool = Field(
        description="True if - Testing: Adding new tests, improving existing tests, or modifying test suites (e.g., unit tests, integration tests)."
    )
    other: bool = Field(
        description="True if - Other: Any other types of work not covered by the above categories (e.g., non-functional changes)."
    )


class DiffAnalyzer(BaseModelThatRemovesTags):
    Summary: str = Field(description="Summary as per given task.")
    Categorization_of_Changes: DevActivityCategories = Field(
        description="Categorization_of_Changes as per given task.",
        examples=[
            {
                "bug_fix": False,
                "documentation": False,
                "feature_enhancement": False,
                "new_feature": False,
                "security": False,
                "tech_debt": True,
                "testing": True,
                "other": False,
            },
        ],
    )
    Maintenance_Relevance: str = Field(description="Maintenance_Relevance as per given task.")
    Description_of_Maintenance_Relevance: str = Field(
        description="Description_of_Maintenance_Relevance as per given task."
    )
    Purpose_of_change: str = Field(description="Purpose_of_Change as per given task.")
    Impact_on_product: str = Field(description="Impact_on_Product as per given task.")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["diff", "title", "description"],
)

llm = get_llm(max_tokens=5_000).with_structured_output(DiffAnalyzer)
diff_analyser_chain = prompt_template | llm

llm = get_llm(max_tokens=5_000, big_text=True).with_structured_output(DiffAnalyzer)
diff_analyser_chain_big_text = get_input_runnable(big_text=True) | prompt_template | llm

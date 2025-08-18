from langchain.prompts import PromptTemplate
from pydantic import Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

summarize_prompt = """
Analyze the provided JSON data containing anomaly and risk insights from Git repositories, JIRA tickets, and database sources. Generate a concise summary as a simple bulleted list where each point:

- Identifies a pattern or issue that appears across data sources
- Names the specific sources affected (repositories, tickets, databases, etc.)
- Describes the nature of the issue in 1-2 concise sentences
- Indicates severity or potential impact when relevant

Format each point like:
- Multiple repositories (repo1, repo2, repo3) contain unsanitized user input in authentication workflows, correlating with database query logs showing repeated SQL error patterns, indicating injection vulnerabilities that could lead to data breaches.
- Code changes in repositories X and Y show consistent deprecation of security validation, while related JIRA tickets reveal recurring authentication issues reported by users, suggesting systemic problems in access control mechanisms.

No section headings, explanations, or additional formatting - just a clean list of findings that highlights cross-system patterns and their significance across Git repositories, JIRA tickets, and database information.Input Data:
Insights json: {insights}
Try to include maximum anomaly and risk insights in summary. Do not miss any insights.
"""


class Summary(BaseModelThatRemovesTags):
    summary: str = Field(
        description="Summary of the provided JSON",
    )


prompt_template = PromptTemplate(
    template=summarize_prompt,
    input_variables=["insights"],
)

llm = get_llm(max_tokens=5000).with_structured_output(Summary) | to_dict_parser
summary_chain = prompt_template | llm

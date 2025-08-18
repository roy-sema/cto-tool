from langchain.prompts import PromptTemplate
from pydantic import Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

system_template = """
Summarize the following JSON containing JIRA completeness data. Structure the summary into the following sections:
    - Overview: Briefly describe what the data represents.
    - Overall Assessment: Analyze the general health/performance based on average scores.
    - Key Findings: Highlight key insights from the top 3 and bottom 3 tickets. Call out patterns, outliers, or notable items.
    - Recommendations: Suggest clear next steps or actions based on the findings.

Input json:
{input_json}

Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON. If it isn't, correct it and return valid JSON only.
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class Summary(BaseModelThatRemovesTags):
    overview: str = Field(description="Overview according to the data")
    overall_assessment: list[str] = Field(description="overall_assessment according to the data")
    key_findings: str = Field(description="key_findings according to the data")
    recommendations: list[str] = Field(description="recommendations according to the data")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["input_json"],
)

llm = get_llm(max_tokens=5000).with_structured_output(Summary) | to_dict_parser
grouped_work_groups_summary_chain = prompt_template | llm

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import to_clean_dict_parser

system_template = """
For each work group object in the input JSON, generate a single summary string that provides a comprehensive paragraph-form analysis of the group's performance data, including interpretation of overall trends, insights from highest and lowest performing tickets, and actionable recommendations for improvement.
Work group data:
{work_group_data}

Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON. If it isn't, correct it and return valid JSON only.
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class Summary(BaseModel):
    summary: str = Field(description="Summary according to the data")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["work_group_data"],
)

llm = get_llm(max_tokens=5000).with_structured_output(Summary) | to_clean_dict_parser
work_group_summary_chain = prompt_template | llm

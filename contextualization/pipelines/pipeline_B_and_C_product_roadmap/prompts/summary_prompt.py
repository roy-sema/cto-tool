from langchain.prompts import PromptTemplate
from pydantic import Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

system_template = """You are tasked with generating a comprehensive summary of git initiatives and their progress. You will receive JSON data containing information about various git-related initiatives, including their completion percentages and justifications. Your task is to transform this technical data into a clear, flowing narrative.

Input JSON file: <json>{input_json}</json>

OUPUT Instructions:
Generate a concise paragraph that:

States total number of initiatives and overall completion average
Categorizes initiatives by status (On Track, At Risk, Behind Schedule)
Uses specific percentages and numbers
Highlights critical delays or achievements
Maintains focus on quantitative metrics over descriptions
Round percentages to whole numbers

Do not include unescaped newlines or invalid characters or bold formatting. Before finalizing the output, validate that the response is well-formed JSON. If it isn't, correct it and return valid JSON only.
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class Summary(BaseModelThatRemovesTags):
    summary: str = Field(description="Summary based on the given json data. [FORMAT_AS_BULLET_POINTS]")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["input_json"],
)

llm = get_llm(max_tokens=5000).with_structured_output(Summary) | to_dict_parser
summary_chain = prompt_template | llm

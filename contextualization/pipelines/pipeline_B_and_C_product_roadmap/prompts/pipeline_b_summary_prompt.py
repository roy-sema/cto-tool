from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

system_template = """
Analyze, organize, and consolidate similar initiatives and epics extracted from multiple summaries while preserving all unique information and context.

**Consolidation Guidelines**

Identify and combine initiatives and epics that represent the same or highly similar goals/objectives
Maintain all unique initiatives and epics, even those appearing minor or infrequently
For initiatives/epics appearing in multiple sources, create comprehensive descriptions by synthesizing all relevant information
Preserve any distinct implementation details, timeline information, or specific technical approaches
Group related epics under their parent initiatives in a hierarchical structure

**Quality Assurance Requirements**

Ensure 100% coverage of all input initiatives and epics in the final consolidated output
Verify descriptions are complete and contain all key details from source descriptions
Check that similar initiatives/epics are properly combined without losing nuanced information
Maintain original technical context, strategic goals, and implementation details when merging descriptions
Standardize terminology while preserving the original meaning

Given the list of initiatives: <json> {list_of_results} </json>
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class Epic(BaseModel):
    epic_name: str = Field(description="Name of the epic")
    epic_description: str = Field(description="Description of the epic")
    epic_percentage: float = Field(description="Percentage of the work completed based on the git data provided")


class Initiative(BaseModel):
    initiative_name: str = Field(description="Name of the initiative")
    initiative_description: str = Field(description="Description of the initiative")
    initiative_percentage: float = Field(description="Percentage of the work completed based on the git data provided")
    epics: list[Epic] = Field(description="List of epics under the initiative")


class Initiatives(BaseModelThatRemovesTags):
    initiatives: list[Initiative] = Field(
        description="List of initiatives with their name, percentage, and justification."
    )


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["list_of_results"],
)

llm = get_llm(max_tokens=7_500).with_structured_output(Initiatives) | to_dict_parser
summary_chain = prompt_template | llm

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import to_clean_dict_parser

system_template = """You are analyzing a git code summary  to extract Initiatives (L1) and Epics (L2). 
Focus only on the code data provided in the git code summary data .You are also provided with purpose of change and impact on product columns. 
Definitions: 
* Initiative (L1): 
A large, strategic body of work representing a significant business objective or investment area. 
Initiatives span multiple quarters or years and focus on business outcomes. 
* Epic (L2): A component of an initiative that represents a substantial functional area. 
Epics typically take 1-3 months to complete and focus on functional capabilities. 
Analyze the git code summary by: 
1. Examining file paths to infer structure and related functionality 
2. Analyzing code changes to understand what's being implemented or modified 
3. Looking for patterns in function/method/class names that suggest business domains 
4. Extracting business intent from comments, docstrings, and documentation 
5. Identifying related changes that might form cohesive functional areas 
6. Inferring relationships between different changed files For each identified 
Epic (L2): 
* Provide a descriptive name reflecting the functional capability 
* Describe what functional value it delivers 
* List the specific files/code changes implementing this epic 
For each identified Initiative (L1): 
* Provide a descriptive name based on the business purpose 
* List the related epics that fall under this initiative 
* Describe the strategic business outcome it addresses
{chat_prompt}
Format your response as: 
Initiatives (L1) 
[Initiative Name 1] 
- Description: [Business purpose] 
- Related Epics: [List of L2 epics]
 - Business Focus: [Strategic outcome] 
 [Initiative Name 2] 
 Epics (L2)
  [Epic Name 1] 
 - Description: [Functional purpose] 
 - Code Location: [Affected files] 
 - User Value: [Capability delivered] 
 - Parent Initiative: [Related L1]
  [Epic Name 2]
  ....
Important Note: Remember that git code summary data provides a limited view of the codebase. Focus on extracting meaningful business categories, not just technical groupings.
Data Provided:
<csv> {csv_schema} </csv>
<csv-data> {csv} </csv-data>
Task for Analysis:
<task> {task} </task>

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


class Initiatives(BaseModel):
    initiatives: list[Initiative] = Field(
        description="List of initiatives with their name, percentage, and justification."
    )


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["csv_schema", "csv", "task", "chat_prompt"],
)

llm = get_llm(max_tokens=5_000).with_structured_output(Initiatives) | to_clean_dict_parser
git_initiatives_chain = prompt_template | llm

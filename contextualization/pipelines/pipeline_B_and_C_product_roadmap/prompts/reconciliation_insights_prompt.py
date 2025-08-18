from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

system_template = """
Analyze the provided Git/VCS initiative JSON dataset to identify and highlight:

Work that lacks proper reconciliation between development and product management activities
1. Extract comprehensive development activity metrics
2. Identify project management patterns and workflows

**For EACH Git Initiative:**
- **Development Activity Metrics:**
  - Percentage of the git commit changes
  
- **Project Management Insights:**
  - Jira ticket completion percentage
  - Highlight initiatives with high development activity but low ticket completion percentage (untracked or poorly managed work)
  - Highlight initiatives with high ticket completion percentage but minimal development activity (over-planning or stale tickets)


- **Reconciliation Flag:**
  - Add a simple "needs_reconciliation" field with value "True" or "False"
  - Set to "True" when:
      - Development activity is significant but Jira ticket completion percentage is low
      - OR Jira ticket completion percentage is high but development activity is minimal
  - Set to "False" otherwise  

Input data:
Git initiatives: {git_initiatives}
Note: Do not include any boilerplate context like here is the json before the actual json output.
IMPORTANT: Do not consider the ticket count to determine the reconciliation flag
"""


class Initiatives(BaseModel):
    work_group: str = Field(description="Work group from VCS or Jira.")
    work_group_type: str = Field(description="Jira or Git based on the input data")
    git_activity: str = Field(description="git activity related to the work group with percentage of changes")
    jira_activity: str = Field(
        description="Jira activity related to the work group with Jira tickets completed along with the highlights"
    )
    needs_reconciliation: bool = Field(description="True or False")


class Insights(BaseModelThatRemovesTags):
    insights: list[Initiatives] = Field(description="Actionable insights for CxO on the given json data.")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["jira_initiatives", "git_initiatives"],
)

llm = get_llm(max_tokens=8000).with_structured_output(Insights) | to_dict_parser
insights_chain = prompt_template | llm

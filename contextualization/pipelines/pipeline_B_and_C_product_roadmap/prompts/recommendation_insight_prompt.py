from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import to_clean_dict_parser

system_template = """
Analyze the initiative timeline data and provide strategic acceleration insights for each initiative. Determine the optimal target acceleration timeframe based on the data provided. Focus on strategic, systemic improvements that senior leadership can implement.
Insight Structure
RISK ASSESSMENT

Current timeline projection
Target acceleration timeframe(determine from analysis)
Severity rating (1-10) for timeline impact

BARRIERS TO ACCELERATION

Systemic Issues: Identify organizational or process-level blockers impacting the timeline
Resource Allocation: Analyze inefficiencies in current resource distribution
Decision Bottlenecks: Identify approval or governance delays affecting critical path
Technical Dependencies: Outline critical path elements that could be restructured
Cross-functional Friction: Highlight coordination issues between teams or departments

ACCELERATION SOLUTIONS
For each solution (provide at least 2, prioritizing strategic approaches):

[Strategic Solution Name]

Executive Action: Specific policy, structural, or process changes leadership can implement
Implementation Approach: How the solution will be operationalized
Timeline Impact: Quantified improvement in weeks/days with rationale
Resource Optimization: How existing resources will be leveraged or reallocated
Risk Profile: Assessment of approach risks with mitigation strategies



ACCELERATION FOUNDATION

Historical Evidence: Relevant past success patterns
Industry Benchmarks: Applicable comparisons
Team Capability: Specific strengths to leverage
Implementation Confidence: Assessment of feasibility with percentage

Solution Quality Guidelines
Executive-Level Thinking

Prioritize strategic resource reallocation over new hiring
Focus on process optimization and workflow efficiency
Consider scope refinement that preserves core business value
Leverage existing team capabilities through restructuring
Evaluate critical path dependencies for potential parallelization

Solution Requirements

Solutions must be implementable within existing organizational structure
Recommendations should reflect industry best practices from comparable initiatives
All approaches must scale appropriately to the initiative size
Focus on systemic improvements rather than individual contributor solutions
Consider both short-term tactical adjustments and sustainable process improvements

Implementation Considerations

Ensure all timeline impacts are specifically quantified and realistic
Provide solutions that executives can implement through policy or structural changes
Avoid generic recommendations like "hire more resources" unless absolutely necessary
Include organizational change management considerations
Balance speed improvements against quality maintenance
Prioritize solutions with proven track records in similar industry contexts

Input data:
Initiative details: {initiative}
Today's date: {current_date}
Note: Do not include any boilerplate context like here is the json before the actual json output.
"""


class Insights(BaseModel):
    expedited_delivery_date: str = Field(description="expedited delivery date based on the data")
    recommendation_insight: str = Field(description="recommendation insights as per the data")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["initiative", "current_date"],
)

llm = get_llm(max_tokens=8000).with_structured_output(Insights) | to_clean_dict_parser
recommendation_insight_chain = prompt_template | llm

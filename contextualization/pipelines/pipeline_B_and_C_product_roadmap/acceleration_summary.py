from langchain.prompts import PromptTemplate

from contextualization.conf.get_llm import get_llm
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import AccelerationSummary, GitInitiatives

system_template = """
Create a very brief, executive-level summary of acceleration recommendations from provided json input. 

Include only:
- The 2 main universal strategies
- One-line recommendation per initiative with weeks of acceleration
- Top 3 key changes needed

Make it extremely concise - suitable for a quick executive briefing. Maximum clarity, minimum words.

<json>
{delivery_estimates}
</json>
"""

prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["delivery_estimates"],
)

llm = get_llm(max_tokens=5000).with_structured_output(AccelerationSummary)
acceleration_summary_chain = prompt_template | llm


async def generate_acceleration_summary(initiatives: list[GitInitiatives]) -> AccelerationSummary | None:
    delivery_estimates = [i.delivery_estimate for i in initiatives.initiatives if i.delivery_estimate]
    if not delivery_estimates:
        return None
    return await acceleration_summary_chain.ainvoke(
        {"delivery_estimates": [i.model_dump() for i in delivery_estimates]}
    )

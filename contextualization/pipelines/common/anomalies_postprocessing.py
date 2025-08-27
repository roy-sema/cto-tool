import logging
from typing import Any

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable

from contextualization.models.anomaly_insights import InsightCategory

anomalies_postprocessing_prompt = """
You will receive a data structure representing an anomaly found in the development process.
Do not change data format, only change the content of the data.
You need to:
- Remove unnecessary empty language that brings no useful information to a non-technical person (if such language exists) from insight description and remove all insight details that are also duplicated in the evidence field from insight description
- remove all references to specific developer or team members. Replace names if any with placeholders 'team member X' where X is a number
- if anomaly itself references limited, absent or insufficient data to generate meaningful insights - set need_to_be_removed to True

### Input Insight:
{insight}
"""

prompt_template_anomalies_postprocessing = PromptTemplate(
    template=anomalies_postprocessing_prompt,
    input_variables=["insight"],
)

logger = logging.getLogger(__name__)


async def postprocess_anomaly_insights(insights: dict[str, Any], llm_chain: Runnable):
    logger.info(f"Postprocessing insights")

    results = await llm_chain.abatch([{"insight": insight} for insight in insights["anomaly_insights"]])
    insights["anomaly_insights"].clear()
    for result in results:
        if result.get("insight_category") == InsightCategory.SECURITY_IMPACT.value:
            # https://semalab.atlassian.net/browse/SIP-673 - dirty hack to fix high-severity security anomalies
            result["significance_score"] = min(result["significance_score"], 8)

        if result["need_to_be_removed"]:
            logger.info(f"Removing insight: {result}")
        else:
            insights["anomaly_insights"].append(result)

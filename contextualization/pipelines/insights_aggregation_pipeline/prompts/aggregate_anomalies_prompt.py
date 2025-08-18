from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

summarize_prompt = """
You are an expert at analyzing patterns across various software development data sources. Your task is to identify similar insights from a provided set of analysis data that may come from different sources.

## Instructions:

1. Analyze each insight in the provided list by carefully examining:
   - The core message in the "insight" field
   - Supporting details in the "evidence" field
   - The "category" classification

2. Link or group insights together when they meet ANY of the following conditions:
   - They point to the same underlying issue or risk, even if described from different perspectives or sources.
   - Contain similar evidence or patterns of development
   - They reflect similar patterns, e.g., frequent rework in Git and recurring reopenings in Jira.
   - One insight provides context or validation for another (e.g., a delay in Jira aligns with a late code merge in Git).
   - They are logically or thematically connected across a shared feature, team, or sprint timeframe.  

3. For each insight you identify as similar to another:
   - Group all similar insights together by their unique_ids
   - Provide a detailed explanation focused on the substantive content similarities
   - Note how insights from different data sources may complement or validate each other

4. Only return insights that have genuine similarities. Do not force connections where none exist.

5. Focus on substantive similarities in meaning and impact, not just superficial text matching.

6. Consider cross-data-source relationships - insights from different systems may reveal connected aspects of the same underlying development pattern.

7. If no similar insights are found, return None.

## Output format:
- similar_insight_ids: List of unique_id of the similar insights
- similarity_reason: Brief explanation of the similarity. Do not reference the IDs within the explanation - focus on the actual content.

Input Data:
Insights json: {insights}
"""


class SimilarAnomaly(BaseModel):
    # primary_insight_id: str = Field(description="The unique_id of the first insight")
    similar_insight_ids: list[str] = Field(
        default_factory=list,
        description="List unique_id's of the similar insights",
    )
    similarity_reason: str = Field(description="Brief explanation of the similarity, start with 'The insights..'")


class Insights(BaseModelThatRemovesTags):
    similar_insights: list[SimilarAnomaly] = Field(
        default_factory=list,
        description="List of similar insights ids, and reason of similarity",
    )


prompt_template = PromptTemplate(
    template=summarize_prompt,
    input_variables=["insights"],
)

llm = get_llm(max_tokens=10000).with_structured_output(Insights) | to_dict_parser
aggregate_anomaly_chain = prompt_template | llm

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.tags import get_tags_prompt
from contextualization.utils.output_parser import to_clean_dict_parser

system_template = """

### **TAG DEFINITIONS**
{tag_definitions}

Transform the processed summaries into a compelling technical overview that highlights key contributions and impact.

Given the input list of summaries: <text> {list_of_summaries} </text>

Essential requirements:

1. Start with dynamic, varied openings - use different sentence structures and avoid repetitive patterns
2. Focus on concrete impact and specific technical details rather than generic descriptions
3. Include precise examples (file names, technologies, metrics) to demonstrate real changes
4. Write conversationally but technically - avoid formal academic language
5. Never mention "summaries," "analysis," or "codebase demonstrates" - speak directly about the code and changes
6. Keep justifications under 100 words when possible
7. Lead with the most interesting or impactful technical detail first
8. [FORMAT_AS_BULLET_POINTS]

Vary your opening styles:
- Start with specific technical achievements
- Lead with concrete metrics or scope
- Begin with the problem solved
- Open with the most significant change
- Start with technology or tool names
"""


class CommitAnalysis(BaseModel):
    response: str = Field(description="Response as per given task.")


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["list_of_summaries"],
    partial_variables={"tag_definitions": get_tags_prompt(format_as_bullet_points=True)},
)
llm = get_llm(max_tokens=2_000).with_structured_output(CommitAnalysis) | to_clean_dict_parser
summary_chain = prompt_template | llm

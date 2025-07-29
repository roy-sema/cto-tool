from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from contextualization.conf.get_llm import get_llm

system_template = """
Refine the text by rephrasing sentences like:
- examples were not identified
Never say that examples were not identified.
Round all percentages to whole numbers.
<text>
{input_text}
</text>
Do not rephrase other sentences.
Do not include boilerplate text like "Here's a refined version" before the actual response.
Do not use first  person pronouns like "I","my","me","mine",etc.
"""

prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["input_text"],
)

llm = get_llm(max_tokens=5000)
refine_explanations_chain = prompt_template | llm | StrOutputParser()

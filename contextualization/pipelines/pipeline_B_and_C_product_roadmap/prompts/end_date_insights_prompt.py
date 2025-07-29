from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from contextualization.conf.get_llm import get_llm

system_template = """
Give a rationale for the estimated_end_date for a Jira initiative based on the given json data.
Why is an initiative expected to be completed by a certain date? What factors are influencing the timeline?

Estimation approach used:
On average, it took {average_time_per_ticket} per ticket to complete.
We estimated estimated_end_date approximately by considering that each ticket takes the same amount of time to complete.
That is approximately an initiative takes {average_time_per_ticket}*{total_tickets}={estimated_total_time} days to complete from the start date.

Input JSON file: <json>{input_json}</json>

OUTPUT Instructions:
Make it only one sentence long.
Do not talk explicitly about the estimation approach.
Use months or weeks as units of time.
Do not add boilerplate context like based on the provided JSON data, here's an explanation.
"""

prompt_template = PromptTemplate(
    template=system_template,
    input_variables=[
        "input_json",
        "average_time_per_ticket",
        "total_tickets",
        "estimated_total_time",
    ],
)

llm = get_llm(max_tokens=5000)
end_date_insights_chain = prompt_template | llm | StrOutputParser()

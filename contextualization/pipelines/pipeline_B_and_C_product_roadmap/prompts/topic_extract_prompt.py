from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import to_clean_dict_parser

#################################################################################################################

topic_modelling_template_git = """
You are an expert at assigning topics to the git commit data based on the git diff summaries.

Instruction:
1. You will be provided with a list of git diff summaries, each representing a separate commit change.
2. Finally, you will be provided with list of topics and its description within <topics> List[topics] </topics>.
3. From the given list of topics, you need to understand the topic, compare the summary associated with the topic and assign the best fit topic to the ticket from the given list.
4. We have a special topic `Other`, which will be assigned when no other topics best match the given ticket.
5. Final output should be a json where json with three keys: topic (name of the topic from given list), reason (reason for assigning the topic), probability (a float between 0 and 1 indicating how closely the topic matches the given git diff summary)
6. Note: Include every row in the output as provided in the <rows> ... </rows> tag. Topics should be strictly from the given topic list.
<diff_summary>
{diff_summary}
</diff_summary>

<topics>
{topic}
</topics>

<task>
{task}
</task>

Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON. If it isn't, correct it and return valid JSON only.
Note: Do not include any boilerplate context like here is the json before the actual json output.
Only assign topic, that is fully related to the summary. DO NOT hallucinate.
"""


class FormatGit(BaseModel):
    # row_number: int = Field(description="The row number in the dataset, provided in rows_data.")
    Categorization_of_initiative_git: str = Field(
        description="The assigned topic or category for the row, providing a high-level summary or classification."
    )
    reason_of_initiative_git: str = Field(
        description="The justification or explanation for assigning the specific topic to the row, giving context and details."
    )
    initiative_relevence_score_git: float = Field(
        description="Confidence score representing the topic's relevance to the git diff summary, ranging from 0.0 (no match) to 1.0 (perfect match)"
    )


prompt_template_2 = PromptTemplate(
    template=topic_modelling_template_git,
    input_variables=["diff_summary", "topic", "task"],
)

# Create the chain
llm = get_llm(max_tokens=8000).with_structured_output(FormatGit) | to_clean_dict_parser
chain_topic_assign_git = prompt_template_2 | llm


#################################################################################################################

topic_modelling_template_assign_to_jira_from_git = """
You are an expert at assigning topics to the Jira tickets based on the description. Also, you are good with interpreting the Jira board from its csv export.

Instruction:
1. You will be provided with a Jira ticket description and you have to assign a topic based on provided topics.
2. Finally, you will be provided with list of topics and its description within <topics> List[topics] </topics>.
3. From the given list of topics, you need to understand the topic, compare the summary associated with the topic and assign the best fit topic to the ticket from the given list.
4. We have a special topic `Other`, which will be assigned when no other topics best match the given ticket.
5. Final output should be a json where json with three keys: topic (name of the topic from given list), reason (reason for assigning the topic), probability (a float between 0 and 1 indicating how closely the topic matches the given Jira ticket)
6. Note: Include every row in the output as provided in the <rows> ... </rows> tag. Topics should be strictly from the given topic list.
<jira_description>
{jira_description}
</jira_description>

<topics>
{topic}
</topics>

<task>
{task}
</task>

Do not include unescaped newlines or invalid characters. Before finalizing the output, validate that the response is well-formed JSON. If it is not, correct it and return valid JSON only.
Note: Do not include any boilerplate context like here is the json before the actual json output.
Only assign topic, that is fully related to the summary. DO NOT hallucinate.
"""


class FormatForJiraGitInitiatives(BaseModel):
    # row_number: int = Field(description="The row number in the dataset, provided in rows_data.")
    Categorization_of_initiative_git: str = Field(
        description="The assigned topic or category for the row, providing a high-level summary or classification."
    )
    reason_of_initiative_git: str = Field(
        description="The justification or explanation for assigning the specific topic to the row, giving context and details."
    )
    initiative_relevence_score_git: float = Field(
        description="Confidence score representing the topic's relevance to the Jira ticket, ranging from 0.0 (no match) to 1.0 (perfect match)"
    )


prompt_template_4 = PromptTemplate(
    template=topic_modelling_template_assign_to_jira_from_git,
    input_variables=["jira_description", "topic", "task"],
)

# Create the chain
llm = get_llm(max_tokens=10_000).with_structured_output(FormatForJiraGitInitiatives) | to_clean_dict_parser
chain_topic_assign_to_jira_from_git = prompt_template_4 | llm

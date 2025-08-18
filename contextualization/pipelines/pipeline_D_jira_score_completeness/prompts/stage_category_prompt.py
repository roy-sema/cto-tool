from typing import Literal

from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

classify_stage_to_category_prompt_template_string = """
You are an expert in JIRA analysis, product management, and scrum practices. 
You will be given a list JIRA ticket stages and you have to classify each stage into categories like "Done", "Will Not Do", "Underway", "Ready for Work", "Backlog" based in the below rules.

### Rules:
1. Rule Set: “Done”. Assign the ticket to Done if: 
    1.1. Status is explicitly done.
    1.2. No further action is required and work has been completed.

2. Rule Set: “Will Not Do”. Assign the ticket to Will Not Do if:
    1.1. Status is explicitly won't do, cancelled, or similar.
    1.2. The work was intentionally skipped or deprioritized.
    1.3. No action is expected in the future.

3. Rule Set: “Underway”. Assign the ticket to Underway if:
    1.1. The work is currently being executed or verified, including:
        1.1.1. Status is in progress, code review, PR review, testing, documentation, or ready to deploy.
    1.2. The ticket shows active effort even if not yet marked complete.

4. Rule Set: “Ready for Work”. Assign the ticket to Ready for Work if:
    4.1. Status is todo or equivalent.
    4.2. Ticket is clearly defined, unblocked, and ready for execution — but no one is actively working on it yet.

5. Rule Set: “Backlog”. Assign the ticket to Backlog if:
    5.1. Status is backlog, product refinement, or technical refinement.
    5.2. Ticket is not ready to be picked up:
        5.2.1. Missing details, still being scoped, or awaiting decisions.
    5.3. Any “refinement” phase suggests preparation, not action.

Input list of JIRA ticket stages:
{jira_ticket_stages}

### Additional Rules (to be followed strictly):
1. Avoid first-person references ("I," "we," "our").
2. Do not ever mention the name of any author or any person explicitly.
3. Strictly see to it that you include all the stages in the final mapping.
"""

# Define the PromptTemplate for the anomaly detection
classify_stage_to_category_prompt_template = PromptTemplate(
    template=classify_stage_to_category_prompt_template_string,
    input_variables=["jira_ticket_stages"],
)


class StageClassifierOutput(BaseModel):
    original_stage: str = Field(description="The original ticket status or stage")
    category: Literal["Done", "Will Not Do", "Underway", "Ready for Work", "Backlog"] = Field(
        description="Mapped categories for each stage"
    )


class StageClassifier(BaseModelThatRemovesTags):
    stage_categories: list[StageClassifierOutput] = Field(
        description="List of dictionaries with ticket status and category"
    )


llm = get_llm(max_tokens=10_000).with_structured_output(StageClassifier) | to_dict_parser
stage_classification_chain = classify_stage_to_category_prompt_template | llm

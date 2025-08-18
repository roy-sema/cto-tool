from langchain.prompts import PromptTemplate
from pydantic import Field

from contextualization.conf.get_llm import get_llm
from contextualization.models.ticket_completeness import TicketCategory
from contextualization.utils.output_parser import BaseModelThatRemovesTags, to_dict_parser

classification_instructions = """
You are an expert Jira classifier. Your job is to categorize a given Jira ticket into one of the following categories:

***Bug***
    A. Definition: A defect, error, or flaw in the software that causes it to produce incorrect or unexpected results, behave in unintended ways, or deviate from requirements.

    B. Key characteristics:

        Reports unexpected behavior of existing functionality

        Often includes steps to reproduce the issue

        May reference specific error messages or logs

        Usually contains severity/priority indicators

        Typically describes both expected and actual behavior

    C. Example patterns:

        "System crashes when..."

        "Error occurs after..."

        "Feature X is not working as expected..."

        "Calculation returns incorrect value..."

***Story***
    A. Definition: A description of a new feature or enhancement from an end-user perspective, focusing on the user's needs, the functionality required, and the value it delivers.

    B. Key characteristics:

        Often follows "As a [user], I want [functionality] so that [benefit]" format

        Describes new capabilities or enhancements to existing features

        Includes acceptance criteria or definition of done

        User-focused rather than system-focused

        Represents a discrete piece of functionality with business value

    C. Example patterns:

        "Add capability to..."

        "Enhance the existing..."

        "Provide users with ability to..."

        "Implement new feature for..."

***Incident***
    A. Definition: An unplanned interruption, degradation, or need for emergency response related to production systems that requires immediate attention and resolution.

    B. Key characteristics:

        Relates to production system issues affecting users

        Often has timestamps and duration information

        May include impact assessment (number of users affected)

        Usually has urgency indicators

        May reference monitoring alerts or customer reports

    C. Example patterns:

        "Production outage of..."

        "Service degradation affecting..."

        "Customer-reported critical issue with..."

        "System downtime incident..."

***Request***
    A. Definition: A formal ask for information, assistance, access, or resources that doesn't involve developing new features or fixing defects.

    B. Key characteristics:

        Seeks information, permissions, or actions rather than development work

        Often involves administrative tasks

        May include approvals or authorizations

        Typically doesn't result in code changes

        Often comes from stakeholders outside the development team

    C. Example patterns:

        "Request access to..."

        "Need information about..."

        "Please provide documentation for..."

        "Assistance required with..."

***Manual Testing***
    A. Definition: Tasks related to human-executed test procedures that verify system functionality, usability, or performance through direct interaction.

    B. Key characteristics:

        Contains specific test cases or scenarios to be executed by a person

        Often includes detailed steps and expected results

        May reference test environments or data

        Focuses on verification and validation activities

        May include exploratory testing or user acceptance testing

    C. Example patterns:

        "Perform user acceptance testing for..."

        "Validate functionality of..."

        "Execute test cases for..."

        "Verify that the system correctly..."

***Automated Testing***
    A. Definition: Tasks related to creating, maintaining, or executing automated test scripts that programmatically verify system functionality, integration, or performance.

    B. Key characteristics:

        Involves writing or modifying test automation code

        References testing frameworks or tools

        May include CI/CD pipeline integration

        Focuses on repeatable, programmatic verification

        Often includes technical implementation details

    C. Example patterns:

        "Create automated tests for..."

        "Update test scripts to include..."

        "Implement integration tests for..."

        "Add unit tests covering..."

***Other***
    A. Definition: Tasks that don't clearly fit into the above categories, including infrastructure work, documentation, research, technical debt, and administrative activities.

    B. Key characteristics:

        Often related to non-functional requirements or system maintenance

        May include research, spikes, or proof-of-concepts

        Could involve documentation, training, or knowledge transfer

        May be related to build, deployment, or infrastructure

        Often cross-cutting or supportive in nature

    C. Example patterns:

        "Research options for..."

        "Update documentation related to..."

        "Set up infrastructure for..."

        "Refactor code to improve..."

        "Create training materials for..."

Examples:
- "System crashes when..." → Bug
- "Add ability for users to..." → Story
- "Production outage of..." → Incident
- "Request access to system..." → Request
- "Perform UAT for..." → Manual Testing
- "Create unit tests for..." → Automated Testing
- "Update documentation..." → Other

You MUST choose exactly one category from the list above.

Return only valid JSON in this format:
{{"llm_category": "<One of the 7 categories above>"}}
"""

system_template = f"""
{classification_instructions}

---
Input Jira ticket:
{{jira_ticket_row}}

"""


class JiraCategory(BaseModelThatRemovesTags):
    llm_category: str = Field(
        description=f"Predicted category of the Jira ticket. One of: [{', '.join([category.value for category in TicketCategory])}]"
    )


prompt_template = PromptTemplate(
    template=system_template,
    input_variables=["jira_ticket_row"],
)

llm = get_llm(max_tokens=10000).with_structured_output(JiraCategory) | to_dict_parser

categorize_chain = prompt_template | llm

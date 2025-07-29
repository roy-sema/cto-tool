import logging

from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from contextualization.conf.get_llm import get_llm
from contextualization.utils.output_parser import to_clean_dict_parser

# Define a system prompt for column filtering without descriptions
column_filter_template = """
You are analyzing a dataset of task-related information. Here are the available column names:

{columns}
and the provided task is:
<task>
{task}
</task>
Based on the given task identify columns which needs to be selected as the most relevant columns.
Return the minimum number of columns as needed (minimum 2 and maximum 4). 
Do not include columns that may have unncessary duplicate information.

Do not include boilerplate text like "here is the json" before the actual response.
"""


class FilterColumns(BaseModel):
    columns: list = Field(description="List of selected columns")


prompt_template = PromptTemplate(
    template=column_filter_template,
    input_variables=["columns", "task"],
)


# Define LLM for column filtering
llm_column_filter = get_llm(max_tokens=2_000).with_structured_output(FilterColumns) | to_clean_dict_parser

# RunnableLambda to process LLM's output and return selected columns
# select_columns = RunnableLambda(lambda x: x['selected_columns'])

# Combine column filtering template with LLM
column_filter_chain = prompt_template | llm_column_filter


# Example function to execute the column filtering process
def filter_columns(df, task):
    try:
        # Get the list of column names
        columns = list(df.columns)

        # Run the chain to filter columns
        selected_columns = column_filter_chain.invoke({"columns": columns, "task": task})
        logging.info(f"filtered columns required to do the analysis::{selected_columns}")

        return selected_columns
    except Exception as e:
        logging.exception(f"Pipeline B/C - Error while selecting Jira columns")

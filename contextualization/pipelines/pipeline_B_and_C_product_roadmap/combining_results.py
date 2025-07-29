import json
import logging
from pathlib import Path
from typing import Any

from contextualization.pipelines.pipeline_B_and_C_product_roadmap.prompts.pipeline_b_summary_prompt import (
    summary_chain,
)


def summarize_git_initiatives(git_data_initiatives: list[dict[str, Any]], output_file: Path) -> dict[str, Any] | None:
    """
    Reads a JSON file containing a list of dictionaries with a 'response' key, combines the responses,
    sends them to an LLM for summarization, and writes the summary to a new JSON file.

    Parameters:
        git_data_initiatives (list): git data initiatives.
        output_file (Path): Path to the output JSON file where the summary will be written.
    """
    try:
        logging.info("Summarizing the git initiatives")
        # Read input JSON file
        logging.info(f"Length of git initiatives loaded to combine the summaries: {len(git_data_initiatives)}")
        # # Extract and combine all 'response' values
        # combined_text = [entry["changes"] for entry in data if "changes" in entry]

        output = summary_chain.invoke({"list_of_results": git_data_initiatives})

        # Add the "Other" category
        other_category = {
            "initiative_name": "Other",
            "initiative_description": "The remaining changes include various miscellaneous updates and enhancements that do not fall under the major categories. These involve minor bug fixes, performance optimizations, and updates to documentation. While individually smaller in impact, collectively, these changes contribute significantly to overall product quality and user experience.",
            "initiative_percentage": 0,
            "epics": [],
        }

        output["initiatives"].append(other_category)

        # Write the summary to the output JSON file
        with open(output_file, "w") as outfile:
            json.dump(output, outfile, indent=4)

        logging.info(f"Final git initiatives results saved to file: {output_file}")
        return output

    except Exception:
        logging.exception(f"Pipeline B/C - An error occurred while summurizing the git initiatives")
        return None

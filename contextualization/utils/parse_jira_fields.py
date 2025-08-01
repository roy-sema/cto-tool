import ast
import logging

import pandas as pd


def parse_changelog_data(changelog_value):
    """Parse the structured data from a single issue's changelog"""
    changelog_entries = []

    if pd.isna(changelog_value) or not changelog_value:
        return changelog_entries

    try:
        if isinstance(changelog_value, str):
            changelog = ast.literal_eval(changelog_value)
        else:
            changelog = changelog_value

        # Case 1: If changelog is NOT dict
        if not isinstance(changelog, dict):
            logging.warning(
                f"Changelog is not a dict.",
                extra={"type": type(changelog), "value": changelog},
            )
            return changelog_entries

        # Case 2: If it's a dict but doesn't have 'histories' key
        if "histories" not in changelog:
            logging.warning(
                f"'histories' key missing in changelog dict.",
                extra={"value": changelog},
            )
            return changelog_entries

        # Normal parsing if dict and has 'histories'
        for history in changelog["histories"]:
            history_id = history.get("id", "unknown")
            author = history.get("author", {}).get("displayName", "Unknown")
            created_date = history.get("created", "")
            for item in history.get("items", []):
                field = item.get("field", "")
                to_value = item.get("toString", "")

                # Special handling for 'labels' field
                if field.lower() == "labels" and isinstance(to_value, str):
                    to_value = to_value.split(" ")

                change_entry = {
                    "history_id": history_id,
                    "author": author,
                    "created": created_date,
                    "field": field,
                    "field_type": item.get("fieldtype", ""),
                    "from_value": item.get("fromString", ""),
                    "to_value": to_value,
                }
                changelog_entries.append(change_entry)

    except Exception:
        logging.exception(
            "Error while parsing the changelog",
            extra={"changelog": changelog},
        )
    return changelog_entries

# Recursively go through the JSON and round the fields provided
from collections.abc import Sequence
from typing import Any


def round_percentages(data: Any, fields: Sequence[str] = ("percentage",)) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in fields:
                data[key] = round(data[key])
            elif isinstance(value, dict | list):
                round_percentages(value, fields)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict | list):
                round_percentages(item, fields)

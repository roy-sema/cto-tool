import json
import logging
from typing import Any

from pydantic import BeforeValidator

from contextualization.models.anomaly_insights import InsightCategory

logger = logging.getLogger(__name__)


# Sometimes LLMs return a JSON-formatted string instead of an object;
# if so, we attempt to parse it into a Python object.
# Sometimes the response has extra characters, like `}` at the end.
def parse_json_string(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            return json.loads(value[: e.pos].rstrip())
    return value


parse_json_string_validator = BeforeValidator(parse_json_string)


def fix_invalid_category(value: Any) -> InsightCategory:
    """Convert a value to InsightCategory, defaulting to OTHER if invalid."""
    try:
        return InsightCategory(value)
    except ValueError:
        logger.warning(f"Invalid category value: {value}")
        return InsightCategory.OTHER


# Create a validator that can be used with Annotated
category_validator = BeforeValidator(fix_invalid_category)

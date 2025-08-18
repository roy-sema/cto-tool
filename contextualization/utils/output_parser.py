from typing import Any

from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, model_validator
from pydantic.v1 import BaseModel as BaseModelV1

from contextualization.conf.rate_limit import NoResponseException
from contextualization.tags import ALL_TAGS


def clean_tags_from_dict(data: Any) -> Any:
    """Recursively clean tags from dictionary values."""
    if isinstance(data, dict):
        return {k: clean_tags_from_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_tags_from_dict(item) for item in data]
    elif isinstance(data, str):
        cleaned = data
        for tag in ALL_TAGS:
            cleaned = cleaned.replace(tag, "")
        return cleaned
    else:
        return data


class BaseModelThatRemovesTags(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def clean_tags_from_data(cls, data: Any) -> Any:
        return clean_tags_from_dict(data)


def parse_raw(parsed: BaseModel | None):
    if not isinstance(parsed, BaseModel | BaseModelV1) or parsed is None:
        raise NoResponseException

    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()
    return parsed.dict()


to_dict_parser = RunnableLambda(parse_raw)

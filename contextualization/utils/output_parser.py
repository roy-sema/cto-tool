from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel
from pydantic.v1 import BaseModel as BaseModelV1

from contextualization.conf.rate_limit import NoResponseException
from contextualization.tags import ALL_TAGS


def clean_tags_from_dict(data):
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


def parse_raw_and_clean(parsed: BaseModel | BaseModelV1):
    if parsed is None:
        raise NoResponseException

    if not isinstance(parsed, (BaseModel, BaseModelV1)):
        raise NoResponseException

    if hasattr(parsed, "model_dump"):
        data = parsed.model_dump()
    else:
        data = parsed.dict()
    return clean_tags_from_dict(data)


to_clean_dict_parser = RunnableLambda(parse_raw_and_clean)

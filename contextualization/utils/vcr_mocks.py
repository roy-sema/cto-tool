import logging
import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any

try:
    from vcr import VCR
    from vcr.record_mode import RecordMode
except ImportError:
    VCR = None
    RecordMode = None

logging.getLogger("vcr").setLevel(logging.CRITICAL)


def before_record_response(response: dict[str, Any]) -> dict[str, Any] | None:
    if response["status"]["code"] != 200:
        return None  # skip recording this response

    # if it's not an anthropic request
    if "anthropic-ratelimit-requests-limit" not in response["headers"]:
        return response

    # To not have sleeps on replay
    limit = response["headers"]["anthropic-ratelimit-requests-limit"]
    response["headers"]["anthropic-ratelimit-requests-remaining"] = limit

    limit = response["headers"]["anthropic-ratelimit-tokens-limit"]
    response["headers"]["anthropic-ratelimit-tokens-remaining"] = limit

    limit = response["headers"]["anthropic-ratelimit-output-tokens-limit"]
    response["headers"]["anthropic-ratelimit-output-tokens-remaining"] = limit

    limit = response["headers"]["anthropic-ratelimit-input-tokens-limit"]
    response["headers"]["anthropic-ratelimit-input-tokens-remaining"] = limit

    return response


def calls_context(pipeline_file_name: str):
    calls_mocked = os.getenv("USE_HTTP_CALL_MOCKS", "False").lower().strip() == "true"
    cassettes_path = os.getenv("CASSETTES_PATH", ".cassettes")
    path = Path(cassettes_path).resolve() / pipeline_file_name

    if not calls_mocked or VCR is None:
        return nullcontext()

    vcr = VCR(
        record_on_exception=False,
        record_mode=RecordMode.NEW_EPISODES,
        match_on=["method", "uri", "body"],
        decode_compressed_response=True,
        ignore_hosts=["api.honeycomb.io"],
        before_record_response=before_record_response,
        serializer="yaml",
    )
    return vcr.use_cassette(path)

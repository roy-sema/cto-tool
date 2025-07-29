import logging
import time
from abc import ABC
from datetime import datetime
from functools import cached_property
from typing import Any, Callable

import anthropic
import httpx
from google.api_core.exceptions import GoogleAPIError, InternalServerError
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.chat_models import _format_messages, convert_to_anthropic_tool
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

RETRY_ERRORS = (
    anthropic.AnthropicError,
    anthropic.APIError,
    anthropic.RateLimitError,
    anthropic.APIStatusError,
    GoogleAPIError,
    InternalServerError,
)


class NoResponseException(Exception):
    pass


logger = logging.getLogger(__name__)


class BaseCustomWithRetry(BaseChatModel, ABC):
    def _wait_if_needed(self) -> None: ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=60 * 3),
        retry=retry_if_exception_type(RETRY_ERRORS),
    )
    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._wait_if_needed()
        return await super()._agenerate(messages, stop, run_manager, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=60 * 3),
        retry=retry_if_exception_type(RETRY_ERRORS),
    )
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._wait_if_needed()
        return super()._generate(messages, stop, run_manager, **kwargs)

    def with_structured_output(self, *args: Any, **kwargs: Any):
        runnable = super().with_structured_output(*args, **kwargs)
        return runnable.with_retry(
            retry_if_exception_type=(
                OutputParserException,
                ValidationError,
                TimeoutError,
                httpx.TimeoutException,
                NoResponseException,
            ),
            stop_after_attempt=5,
            wait_exponential_jitter=True,
        )


class RateLimitedChatAnthropic(BaseCustomWithRetry, ChatAnthropic):
    requests_min_wait_until: float = 0
    tokens_min_wait_until: float = 0
    retry_after: float = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @cached_property
    def _client(self) -> anthropic.Client:
        client_params = self._client_params

        client = httpx.Client(
            headers={
                "Connection": "close",
            },
            event_hooks={"request": [], "response": [self.custom_response_hook]},
        )
        client_params["http_client"] = client
        return anthropic.Client(**client_params)

    @cached_property
    def _async_client(self) -> anthropic.AsyncClient:
        client_params = self._client_params

        client = httpx.AsyncClient(
            headers={
                "Connection": "close",
            },
            event_hooks={"request": [], "response": [self.acustom_response_hook]},
        )
        client_params["http_client"] = client
        return anthropic.AsyncClient(**client_params)

    async def acustom_response_hook(self, response: httpx.Response):
        self.custom_response_hook(response)

    def custom_response_hook(self, response: httpx.Response):
        try:
            if response.status_code == 429:
                self.retry_after = float(response.headers.get("retry-after", 0))
                self._wait_if_needed()
                return

            rate_limit_headers = {
                key: value for key, value in response.headers.items() if key.lower().startswith("anthropic-ratelimit")
            }
            if not rate_limit_headers:
                return

            self._process_rate_limit_headers(rate_limit_headers)
        except Exception:
            logger.exception("Error on rate limit hook")

    def _process_rate_limit_headers(self, headers: dict[str, str]) -> None:
        if "anthropic-ratelimit-requests-remaining" in headers and "anthropic-ratelimit-requests-reset" in headers:
            requests_remaining = int(headers["anthropic-ratelimit-requests-remaining"])
            requests_limit = int(headers["anthropic-ratelimit-requests-limit"])
            requests_threshold = requests_limit * 0.1

            if requests_remaining <= requests_threshold:
                reset_date = headers["anthropic-ratelimit-requests-reset"]
                requests_reset = datetime.fromisoformat(reset_date).timestamp()
                self.requests_min_wait_until = max(requests_reset, self.requests_min_wait_until)

        if (
            "anthropic-ratelimit-output-tokens-remaining" in headers
            and "anthropic-ratelimit-output-tokens-reset" in headers
        ):
            tokens_remaining = int(headers["anthropic-ratelimit-output-tokens-remaining"])
            tokens_limit = int(headers["anthropic-ratelimit-output-tokens-limit"])
            token_threshold = tokens_limit * 0.3

            # If tokens are running low (less than 30% remaining), prepare to wait
            if tokens_remaining <= token_threshold:
                reset_date = headers["anthropic-ratelimit-output-tokens-reset"]
                tokens_reset = datetime.fromisoformat(reset_date).timestamp()
                self.tokens_min_wait_until = max(tokens_reset, self.tokens_min_wait_until)

        if (
            "anthropic-ratelimit-input-tokens-remaining" in headers
            and "anthropic-ratelimit-input-tokens-reset" in headers
        ):
            tokens_remaining = int(headers["anthropic-ratelimit-input-tokens-remaining"])
            tokens_limit = int(headers["anthropic-ratelimit-input-tokens-limit"])
            token_threshold = tokens_limit * 0.1

            # If tokens are running low (less than 10% remaining), prepare to wait
            if tokens_remaining <= token_threshold:
                reset_date = headers["anthropic-ratelimit-input-tokens-reset"]
                tokens_reset = datetime.fromisoformat(reset_date).timestamp()
                self.tokens_min_wait_until = max(tokens_reset, self.tokens_min_wait_until)

    def _wait_if_needed(self) -> None:
        current_time = time.time()

        wait_until = max(self.requests_min_wait_until, self.tokens_min_wait_until)
        wait_seconds = max(wait_until - current_time, self.retry_after)

        if wait_seconds > 0:
            logger.info(f"{self.requests_min_wait_until=} {self.tokens_min_wait_until=} {self.retry_after=}")
            logger.info(f"Rate limit approaching. Waiting for {wait_seconds + 5:.2f} seconds")
            time.sleep(wait_seconds + 5)

        self.tokens_min_wait_until = 0
        self.requests_min_wait_until = 0
        self.retry_after = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=60, max=60 * 3),
        retry=retry_if_exception_type(RETRY_ERRORS),
    )
    async def aget_num_tokens_from_messages(
        self,
        messages: list[BaseMessage],
        tools: list[dict[str, Any] | type | Callable | BaseTool] | None = None,
        **kwargs: object,
    ) -> int:
        formatted_system, formatted_messages = _format_messages(messages)
        if isinstance(formatted_system, str):
            kwargs["system"] = formatted_system
        if tools:
            kwargs["tools"] = [convert_to_anthropic_tool(tool) for tool in tools]

        response = await self._async_client.beta.messages.count_tokens(
            betas=["token-counting-2024-11-01"],
            model=self.model,
            messages=formatted_messages,  # type: ignore[arg-type]
            **kwargs,
        )
        return response.input_tokens


class ChatGemini(ChatGoogleGenerativeAI, BaseCustomWithRetry): ...

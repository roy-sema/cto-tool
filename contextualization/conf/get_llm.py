from langchain_core.rate_limiters import InMemoryRateLimiter

from contextualization.conf.config import get_config
from contextualization.conf.rate_limit import ChatGemini, RateLimitedChatAnthropic

DEFAULT_MAX_TOKENS = 2000


def get_llm(max_tokens: int = DEFAULT_MAX_TOKENS, big_text: bool = False):
    llm_config = get_config(big_text)
    model = llm_config.model
    temperature = llm_config.temperature

    rate_limiter = InMemoryRateLimiter(
        requests_per_second=llm_config.request_per_second,
        check_every_n_seconds=0.1,  # Frequency to check if a request can be made
        max_bucket_size=10,  # Maximum burst size
    )
    if llm_config.name == "claude":
        return RateLimitedChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            rate_limiter=rate_limiter,
            max_retries=2,
            default_request_timeout=600,
        )
    elif llm_config.name == "gemini":
        return ChatGemini(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            transport="rest",
            rate_limiter=rate_limiter,
        )
    else:
        raise ValueError(f"LLM - {llm_config.name} - not supported. See config.yaml.")

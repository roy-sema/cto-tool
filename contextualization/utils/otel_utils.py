import contextlib
from collections.abc import Generator
from typing import Any

from pysh import env


@contextlib.contextmanager
def suppress_prompt_logging(func: Any = None) -> Generator[None, None, None]:
    with env(TRACELOOP_TRACE_CONTENT="false"):
        yield

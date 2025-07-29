import contextlib

from pysh import env


@contextlib.contextmanager
def suppress_prompt_logging(func=None):
    with env(TRACELOOP_TRACE_CONTENT="false"):
        yield

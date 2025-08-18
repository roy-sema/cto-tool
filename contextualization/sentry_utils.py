import datetime
import logging
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import sentry_sdk
import sentry_sdk.serializer
from opentelemetry import trace
from sentry_sdk.integrations.langchain import SentryLangchainCallback
from sentry_sdk.types import Event, Hint

logger = logging.getLogger(__name__)


def _handle_error(self: Any, run_id: UUID, error: Any) -> None:
    # type: (UUID, Any) -> None
    if not run_id or run_id not in self.span_map:
        return

    span_data = self.span_map[run_id]
    if not span_data:
        return
    span_data.span.__exit__(None, None, None)
    del self.span_map[run_id]


# Sentry has Langcain integration enabled by default which gives us some useful information about LLM calls.
# However default implementation is sending sentry event for each captured exception - even if it's retried
# by langchain's with_retry. It's quite confusing to see errors which are not affecting pipeline execution, so here we're patching
# internal default imlementation.
# Approach is very hacky on likely can be broken by sentry package updates.
SentryLangchainCallback._handle_error = _handle_error


def before_send(event: Event, hint: Hint) -> Event | None:
    try:
        timestamp = event.get("timestamp")
        current_span = trace.get_current_span()
        if not current_span:
            return event
        context = current_span.get_span_context()
        if not context:
            return event
        trace_id = format(context.trace_id, "032x")
        span_id = format(context.span_id, "016x")
        if not (trace_id and span_id and timestamp and trace_id != "00000000000000000000000000000000"):
            return event
        # We convert timestamp to a string because the type hint in sentry
        # is invalid but we gotta make sure it's a string to avoid possible
        # errors
        timestamp_as_number = int(datetime.datetime.fromisoformat(str(timestamp).rstrip("Z")).timestamp())
        event["contexts"] = event.get("contexts", {})
        event["contexts"]["honeycomb"] = {
            "trace": (
                # Intentionally hardcoded for now
                f"https://ui.honeycomb.io/"
                f"stas-semasoftware/environments/sip-prod-1/datasets/sema-sip/trace?"
                f"trace_id={trace_id}&"
                f"span={span_id}&"
                f"trace_start_ts={timestamp_as_number - 50000}&"
                f"trace_end_ts={timestamp_as_number + 50000}"
            )
        }
    except Exception as e:
        # We use warning because sentry would catch exceptions
        # which could cause an infinite loop. Please, don't use
        # exc_info=e for any other situation, this is a super special case.
        logger.warning("Error adding honeycomb trace to sentry event", exc_info=e)

    return event


def filter_transactions(event: Event, hint: Hint) -> Event | None:
    request = event.get("request")
    if not request:
        return event

    url_string = request.get("url")
    if not url_string:
        return event

    parsed_url = urlparse(str(url_string))

    if parsed_url.path == "/health-check/":
        return None

    return event


def init_sentry(environment: str, sentry_dsn: str | None = None):
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1,
        profiles_sample_rate=1,
        send_default_pii=True,
        environment=environment,
        max_value_length=4096,
        before_send_transaction=filter_transactions,
        before_send=before_send,
        ignore_errors=[KeyboardInterrupt],
        _experiments={"enable_logs": True},
    )
    sentry_sdk.serializer.MAX_DATABAG_BREADTH = 50
    sentry_sdk.serializer.MAX_DATABAG_DEPTH = 10

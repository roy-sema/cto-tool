import contextlib
import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.context.context import Context
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource


class OtlpLoggingHandler(LoggingHandler):
    def __init__(self, level=logging.INFO, logger_provider=None):
        resource = Resource(attributes={})
        provider = LoggerProvider(resource=resource)
        processor = BatchLogRecordProcessor(OTLPLogExporter())
        provider.add_log_record_processor(processor)
        super().__init__(level, logger_provider)

    @staticmethod
    def _get_attributes(record: logging.LogRecord):
        attributes = LoggingHandler._get_attributes(record)
        return {k: v if isinstance(v, (bool, str, bytes, int, float)) else str(v) for k, v in attributes.items()}


def get_otel_attributes_from_parent_span(*attrs: str) -> dict[str, Any]:
    span = trace.get_current_span()
    attributes = getattr(span, "_attributes", {})
    return {k: v for k, v in attributes.items() if k in attrs}


@contextlib.contextmanager
def start_span_in_linked_trace(
    tracer: trace.Tracer,
    name: str,
    *,
    prefix: str = "",
    attributes: dict[str, Any] | None = None,
):
    attributes = attributes or {}

    with tracer.start_as_current_span(
        prefix + name,
        attributes=attributes,
        kind=trace.SpanKind.CLIENT,
    ) as parent:
        with tracer.start_as_current_span(
            name,
            attributes=attributes,
            #  empty context means that new trace is created
            context=Context(),
            kind=trace.SpanKind.SERVER,
            links=[trace.Link(parent.get_span_context())],
        ) as span:
            parent.add_link(span.get_span_context())
            yield span

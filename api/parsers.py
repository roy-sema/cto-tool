import codecs

from django.conf import settings
from rest_framework import renderers
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser
from rest_framework.settings import api_settings
from rest_framework.utils import json
from sentry_sdk import capture_exception, push_scope

from mvp.utils import traceback_on_debug


# from https://stackoverflow.com/questions/47662496/how-to-access-request-body-when-using-django-rest-framework-and-avoid-getting-ra
class BodySavingJSONParser(BaseParser):
    """
    Parses JSON-serialized data while keeping the body accessible through raw_body
    """

    media_type = "application/json"
    renderer_class = renderers.JSONRenderer
    strict = api_settings.STRICT_JSON

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as JSON and returns the resulting data.
        """
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        request = parser_context.get("request")

        try:
            decoded_stream = codecs.getreader(encoding)(stream)
            decoded_content = decoded_stream.read()
            # Saving decoded request original body to original_body
            setattr(request, "raw_body", decoded_content)
            parse_constant = json.strict_constant if self.strict else None
            return json.loads(decoded_content, parse_constant=parse_constant)
        except ValueError as exc:
            traceback_on_debug()
            with push_scope() as scope:
                scope.set_extra("request", request)
                scope.set_extra("encoding", encoding)
                capture_exception(exc)
            raise ParseError("JSON parse error - %s" % str(exc))

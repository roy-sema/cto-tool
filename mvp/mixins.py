import inspect
import logging
import re
import subprocess
import sys

from django.conf import settings
from hashids import Hashids
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class PublicIdMixin:
    def public_id(self):
        hashids = Hashids(salt=settings.HASH_SALT, min_length=settings.HASH_MIN_LENGTH)
        return hashids.encode(self.pk)


class DecodePublicIdMixin:
    @staticmethod
    def decode_id(encoded_id):
        hashids = Hashids(salt=settings.HASH_SALT, min_length=settings.HASH_MIN_LENGTH)
        decoded_data = hashids.decode(encoded_id)
        return decoded_data[0] if decoded_data else None


class CommandNameMixin:
    def get_command_name(self):
        for _name, obj in inspect.getmembers(sys.modules[self.__module__]):
            if (
                inspect.isclass(obj)
                and issubclass(obj, CommandNameMixin)
                and obj not in (CommandNameMixin, SingleInstanceCommandMixin)
            ):
                return obj.__module__.split(".")[-1]

        raise Exception("No command class implementing CommandNameMixin found in module.")


class SingleInstanceCommandMixin(CommandNameMixin):
    def is_command_running(self, command):
        process = f"manage.py {command}"
        # uv run creates its own process, so we need to check for both
        process_with_uv_run = r"uv run .+" + process

        try:
            output = subprocess.check_output(["ps", "aux"]).decode("utf-8").lower()
        except subprocess.CalledProcessError:
            return False
        return (output.count(process.lower()) - len(re.findall(process_with_uv_run, output))) > 1

    def run_from_argv(self, argv):
        command_name = self.get_command_name()
        if self.is_command_running(command_name):
            logger.info(f"Command '{command_name}' is already running.")
            sys.exit(1)
        else:
            super().run_from_argv(argv)


class InstrumentedCommandMixin(CommandNameMixin):
    def execute(self, *args, **kwargs):
        with tracer.start_as_current_span(self.get_command_name(), attributes={"args": list(args), **kwargs}):
            super().execute(*args, **kwargs)

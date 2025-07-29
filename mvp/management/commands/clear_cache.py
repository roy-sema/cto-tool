import logging

from django.core.cache import cache
from django.core.management.base import BaseCommand
from sentry_sdk.crons import monitor

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin

logger = logging.getLogger(__name__)


class Command(
    SingleInstanceCommandMixin,
    InstrumentedCommandMixin,
    BaseCommand,
):
    help = "Clears app cache."

    @monitor(monitor_slug="clear_cache")
    def handle(self, *args, **options):
        cache.clear()

        logger.info(f"Successfully cleared cache.")

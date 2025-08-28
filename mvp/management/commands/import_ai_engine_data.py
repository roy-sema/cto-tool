from django.core.management.base import BaseCommand
from sentry_sdk.crons import monitor

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.tasks import ImportAIEngineDataTask


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Imports AI Engine data from CSV for full scans."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

        parser.add_argument(
            "--repoid",
            type=str,
            help="Narrow execution just to given repository ID.",
        )

        parser.add_argument(
            "--commit_sha",
            type=str,
            help="Narrow execution just to given SHA.",
        )

        parser.add_argument(
            "--erase",
            action="store_true",
            help="Erase existing analysis from the database before importing.",
        )

    @monitor(monitor_slug="import_ai_engine_data")
    def handle(self, *args, **options):
        organization_id = options.get("orgid")
        repository_id = options.get("repoid")
        commit_sha = options.get("commit_sha")
        erase = options.get("erase", False)

        ImportAIEngineDataTask().run(
            organization_id=organization_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            erase=erase,
        )

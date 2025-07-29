from django.core.management.base import BaseCommand

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import RepositoryPullRequest
from mvp.tasks import ImportAIEngineDataTask


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Imports AI Engine data from CSV for given Pull Request."

    def add_arguments(self, parser):
        parser.add_argument(
            "prid",
            type=int,
            help="Import given PR ID (not number).",
        )

        parser.add_argument(
            "--erase",
            action="store_true",
            help="Erase existing PR analysis before importing.",
        )

    def handle(self, *args, **options):
        pull_request_id = options.get("prid")
        erase = options.get("erase", False)

        pull_request = self.get_pull_request(pull_request_id)
        if not pull_request:
            self.stdout.write(self.style.ERROR(f"Pull Request not found. Remember to use PR ID, not number."))
            return

        ImportAIEngineDataTask().process_commit(
            pull_request.repository,
            pull_request.head_commit(),
            pull_request=pull_request,
            erase=erase,
        )

    def get_pull_request(self, pull_request_id):
        try:
            return RepositoryPullRequest.objects.get(id=pull_request_id)
        except RepositoryPullRequest.DoesNotExist:
            return None

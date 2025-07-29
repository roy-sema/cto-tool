from django.core.management.base import BaseCommand
from sentry_sdk.crons import monitor

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.tasks import DownloadRepositoriesTask


class Command(
    SingleInstanceCommandMixin,
    InstrumentedCommandMixin,
    BaseCommand,
):
    help = "Fetch repositories from git providers, add them to the database and clone them to disk."

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

        parser.add_argument(
            "--reponame",
            type=str,
            help="Narrow execution just to given repository name.",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-download of repositories. If they exist, they will be deleted and re-downloaded.",
        )

    @monitor(monitor_slug="download_repositories")
    def handle(self, *args, **options):
        organization_id = options.get("orgid", None)
        repository_name = options.get("reponame", None)
        force = options.get("force", False)

        DownloadRepositoriesTask().run(
            organization_id=organization_id,
            repository_name=repository_name,
            force=force,
        )

import logging

from django.core.management.base import BaseCommand, CommandError

from api.tasks import RecalculateCommitAICompositionTask
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import RepositoryCommit

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Recalculates pre-computed AI fields for commits and their related PRs, repositories and groups."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

        parser.add_argument(
            "--repoid",
            type=int,
            help="Narrow execution just to given repository ID.",
        )

        parser.add_argument(
            "--commit_sha",
            type=str,
            help="Narrow execution just to given SHA.",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-calculation on all files, not just those that need it according to attestation.",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Recalculate all commits in the database. (Expensive!)",
        )

    def handle(self, *args, **options):
        organization_id = options.get("orgid")
        repository_id = options.get("repoid")
        commit_sha = options.get("commit_sha")
        force = options.get("force", False)
        is_all = options.get("all", False)

        if not self.has_options(organization_id, repository_id, commit_sha) and not is_all:
            raise CommandError(
                f"You must provide at least one of the following arguments: --orgid, --repoid, --commit_sha"
            )

        if is_all and not self.confirm():
            self.stdout.write(self.style.WARNING("Aborted."))
            return

        RecalculateCommitAICompositionTask().run(
            self.get_commits(organization_id, repository_id, commit_sha),
            force=force,
        )

    def get_commits(self, organization_id=None, repository_id=None, commit_sha=None):
        qs = RepositoryCommit.objects

        if organization_id:
            qs = qs.filter(repository__organization_id=organization_id)

        if repository_id:
            qs = qs.filter(repository_id=repository_id)

        if commit_sha:
            qs = qs.filter(sha=commit_sha)

        return qs.all()

    def has_options(self, organization_id, repository_id, commit_sha):
        return bool(organization_id or repository_id or commit_sha)

    def confirm(self):
        self.stdout.write(
            self.style.WARNING(
                "This command will run on all the commits in the database and might take a very long time."
            )
        )

        confirmation = input(f"Are you sure you want to run it? [y/N] ").lower()

        return confirmation == "y"

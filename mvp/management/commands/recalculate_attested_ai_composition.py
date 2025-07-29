import logging

from django.core.management.base import BaseCommand
from django.db.models import F, Q
from sentry_sdk.crons import monitor

from api.tasks import RecalculateCommitAICompositionTask
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import RepositoryCommit

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Obtains list of commits that have been attested and then Recalculates pre-computed AI fields for the commits and their related PRs, repositories and groups."

    @monitor(monitor_slug="recalculate_attested_ai_composition")
    def handle(self, *args, **options):
        commits = self.get_commits()

        if not commits:
            self.stdout.write(self.style.SUCCESS("Everything up to date!"))
        else:
            RecalculateCommitAICompositionTask().run(list(commits))

            self.stdout.write(self.style.SUCCESS(f"Composition recalculated for {len(commits)} commits!"))

    def get_commits(self):
        return RepositoryCommit.objects.filter(
            Q(last_recalculated_at__lt=F("last_attested_at"))
            | Q(
                last_recalculated_at__isnull=True,
                last_attested_at__isnull=False,
            )
        )

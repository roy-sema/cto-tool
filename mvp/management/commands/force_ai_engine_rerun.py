import logging

from django.core.management.base import BaseCommand

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.tasks import ForceAiEngineRerunTask

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Forces the re-run of the AI Engine for the last analysis of the given organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "orgid",
            type=int,
            help="ID of the organization to re-run analysis.",
        )

        parser.add_argument(
            "--repoid",
            type=str,
            help="Narrow execution just to given repository ID.",
        )

        parser.add_argument(
            "--commit_sha",
            type=str,
            help="Re-run analysis on this SHA instead of the last one.",
        )

        parser.add_argument(
            "--redownload",
            action="store_true",
            help="Force re-download of files. If they exist, they will be deleted and re-downloaded.",
            default=False,
        )

    def handle(self, *args, **options):
        organization_id = options.get("orgid")
        repository_id = options.get("repoid")
        commit_sha = options.get("commit_sha")
        redownload = options.get("redownload", False)

        task = ForceAiEngineRerunTask()

        organization = task.get_organization(organization_id)
        if not organization:
            self.stdout.write(self.style.ERROR(f"Organization not found."))
            return

        commits = task.get_commits(organization_id, repository_id, commit_sha)
        if not commits:
            self.stdout.write(self.style.WARNING(f"No commits found."))
            return

        if self.confirm(organization, commits, redownload):
            if redownload:
                task.redownload_commits(commits, organization)

            task.delete_analysis_files(commits)
            updated = task.mark_commits_pending(commits)
            self.stdout.write(self.style.SUCCESS(f"{updated} commits marked for analysis"))
        else:
            self.stdout.write(self.style.WARNING("Operation cancelled."))

    def confirm(self, organization, commits, redownload=False):
        self.stdout.write(
            "This command deletes the analysis done by the AI Engine for selected commits and marks them as pending so it re-runs."
        )

        if redownload:
            self.stdout.write(self.style.WARNING("The commit files will be deleted if they exist and re-downloaded."))

        num_commits = len(commits)
        self.stdout.write(f"\nOrganization: {organization.name}")
        self.stdout.write(f"Commits ({num_commits}):")
        for commit in commits:
            self.stdout.write(f"- {commit.repository.name} · SHA: {commit.sha}")

        self.stdout.write(self.style.WARNING("\nThis operation is not reversible."))

        confirmation = input(
            f"Are you sure you want to delete the analysis from {num_commits} commits in '{organization.name}' organization? [y/N] "
        ).lower()

        return confirmation == "y"

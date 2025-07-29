import logging

from django.core.management.base import BaseCommand

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import Organization, Repository, RepositoryCommit

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Copies the values in the repository languages field to repository commits."

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
            "--force",
            action="store_true",
            help="overwrite the language field even if it's not empty",
        )

    def handle(self, *args, **options):
        organization_id = options.get("orgid", None)
        repository_id = options.get("repoid", None)
        forced = options.get("force", False)

        commits = RepositoryCommit.objects.prefetch_related("repository")

        if organization_id:
            organization = Organization.objects.get(id=organization_id)
            logger.info(f"organization name: {organization.name}")
            commits = commits.filter(repository__organization_id=organization_id)

        if repository_id:
            repository = Repository.objects.get(id=repository_id)
            logger.info(f"repository name: {repository.full_name()}")
            commits = commits.filter(repository_id=repository_id)

        commits_count = str(commits.count())

        message = self.get_confirmation_message(organization_id, repository_id, forced, commits_count)
        if input(message).lower() != "y":
            self.stdout.write(self.style.WARNING("Aborted."))
            exit()

        logger.info("Processing...")
        processed_commits = 0
        for commit in commits:
            # had to do it this way, filtering on json doesn't seem to work properly
            if not commit.languages or forced:
                commit.languages = commit.repository.languages
                commit.save()
                processed_commits += 1

        self.stdout.write(self.style.SUCCESS(f"Processed {processed_commits} commits."))

    def get_confirmation_message(self, organization_id, repository_id, forced, commits_count):
        message = "This command will "
        if not organization_id and not repository_id:
            message += "run on all organizations and will "
        message += f"process {self.style.WARNING(commits_count)} commits"
        if forced:
            message += f" in {self.style.ERROR('force')} mode"
        message += ". Are you sure you want to proceed? [y/N] "
        return message

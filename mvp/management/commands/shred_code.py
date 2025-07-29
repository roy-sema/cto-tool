import logging
import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from sentry_sdk import capture_exception
from sentry_sdk.crons import monitor

from mvp.mixins import InstrumentedCommandMixin
from mvp.models import (
    Repository,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
    RepositoryPullRequest,
)
from mvp.utils import shred_path, traceback_on_debug

logger = logging.getLogger(__name__)


class Command(InstrumentedCommandMixin, BaseCommand):
    help = "Deletes code from disk for commits created more than 30 days ago. Excludes open Pull Requests and the last commit of each repository."

    DAYS_THRESHOLD = 30

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

    @monitor(monitor_slug="shred_code")
    def handle(self, *args, **options):
        organization_id = options.get("orgid")
        repositories = self.get_repositories(organization_id)

        for repository in repositories:
            self.process_repository(repository)

    def get_repositories(self, organization_id=None):
        qs = Repository.objects

        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        return qs.all()

    def process_repository(self, repository):
        logger.info(f"Processing repository {repository.full_name()}...")
        commits = self.get_shreddable_commits(repository)

        logger.info(f"Found {commits.count()} commits to shred")

        for commit in commits:
            try:
                path = commit.get_download_directory()
                if os.path.exists(path):
                    logger.info(f"Shredding {path}...")
                    shred_path(path)
                else:
                    logger.warning(f"Path {path} does not exist")
            except Exception as e:
                traceback_on_debug()
                capture_exception(e)

            commit.shredded = True
            commit.save()

            logger.info(f"Commit {commit.sha} marked as shredded")

    def get_shreddable_commits(self, repository, days=None):
        time_threshold = timezone.now() - timedelta(days=days or self.DAYS_THRESHOLD)

        keep_shas = []
        if repository.last_commit_sha:
            keep_shas.append(repository.last_commit_sha)

        keep_shas.extend(list(self.get_open_prs_shas(repository)))

        if keep_shas:
            logger.info("Keeping SHAs:")
            for sha in keep_shas:
                logger.info(f"  {sha}")

        commits = RepositoryCommit.objects.filter(
            repository=repository,
            status=RepositoryCommitStatusChoices.ANALYZED,
            shredded=False,
            created_at__lt=time_threshold,
        ).exclude(sha__in=keep_shas)

        return commits.all()

    def get_open_prs_shas(self, repository):
        return RepositoryPullRequest.objects.filter(repository=repository, is_closed=False).values_list(
            "head_commit_sha", flat=True
        )

import logging
import time
from datetime import timedelta

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from sentry_sdk.crons import monitor

from api.tasks import ProcessPullRequestTask
from compass.integrations.integrations import (
    GitBaseIntegration,
    GitRepositoryData,
    PullRequestData,
    get_git_provider_integration,
    get_git_providers,
)
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import DataProviderConnection, Organization, Repository, RepositoryPullRequest

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Fetch pull requests from git providers that were not received through webhooks, and process them."

    API_RATE_LIMIT_DELAY_SECONDS = 1
    PR_THRESHOLD_MINUTES = 10

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

        parser.add_argument(
            "--providers",
            type=str,
            nargs="+",
            help="Narrow execution to just the given provider(s).",
        )

    @monitor(monitor_slug="fetch_pull_requests")
    def handle(self, *args, **options):
        organization_id = options.get("orgid")
        providers = options.get("providers", [])
        if not self.validate_providers(providers):
            return

        organizations = self.get_organizations(organization_id=organization_id)

        for organization in organizations:
            try:
                self.process_organization(organization, providers)
            except Exception:
                logger.exception(
                    "Failed to process organization in fetch pull requests",
                    extra={"organization": organization.name, "providers": providers},
                )

    def process_organization(self, organization: Organization, providers: [str] = None):
        logger.info(f"Fetching PRs for organization '{organization.name}'...")

        connections = self.get_organization_connections(organization, providers)

        num_processed = 0
        for connection in connections:
            if not connection.is_connected():
                logger.warning(
                    f"Skipping connection for organization - not connected",
                    extra={"provider": connection.provider.name, "organization": organization.name},
                )
                continue
            num_processed += self.process_connection(organization, connection)

        logger.info(f"{num_processed} PRs processed for organization '{organization.name}'")

    def process_connection(self, organization: Organization, connection: DataProviderConnection):
        logger.info(
            f"Fetching repositories from '{connection.provider.name}' for organization '{organization.name}'..."
        )

        integration = get_git_provider_integration(connection.provider)
        if not integration:
            return False

        repositories = integration.get_connected_repositories_with_integration(connection)

        num_processed = 0
        for repository_data, integration in repositories:
            num_processed += self.process_repository(organization, integration, repository_data)

        integration.get_missing_pull_requests(
            repository_data=[repo[0] for repo in repositories],
            organization=organization,
        )

        return num_processed

    def process_repository(
        self,
        organization: Organization,
        integration: GitBaseIntegration,
        repository_data: GitRepositoryData,
    ):
        repository = self.get_repository(organization, repository_data.id)
        if not repository:
            logger.warning(f"Repository '{repository_data.owner}/{repository_data.name}' not found in database")
            return 0

        logger.info(f"Fetching PRs for repository '{repository.full_name()}'...")

        # TODO: save last date of processed pull request after polling in the database
        # to avoid processing PRs multiple times.
        # This is tricky because we have to make sure we didn't miss any PRs in the past.
        since = organization.created_at
        until = timezone.now() - timedelta(minutes=self.PR_THRESHOLD_MINUTES)

        try:
            time.sleep(self.API_RATE_LIMIT_DELAY_SECONDS)
            pull_requests = integration.get_repository_pull_requests(
                repository_data, since=since, until=until, state="all"
            )
        except Exception as error:
            # There's no access to the repository
            if isinstance(error, requests.exceptions.HTTPError) and error.response.status_code == 403:
                logger.warning(f"Skipping repository '{repository.full_name()}' - no access")
                # TODO: mark repo as "inactive" in the database to avoid fetching it again
                return 0

            logger.exception(
                "Failed to fetch Pull Requests",
                extra={
                    "provider": integration.provider.name,
                    "repository": repository.full_name(),
                    "organization": repository.organization.name,
                    "repository_data": repository_data,
                },
            )

            return 0

        if not pull_requests:
            logger.info(f"No PRs found for repository '{repository.full_name()}'")
            return 0

        num_processed = 0
        for pull_request_data in pull_requests:
            processed = self.process_pull_request(integration, repository, repository_data, pull_request_data)
            if processed:
                num_processed += 1

        return num_processed

    def process_pull_request(
        self,
        integration: GitBaseIntegration,
        repository: Repository,
        repository_data: GitRepositoryData,
        pull_request_data: dict,
    ):
        try:
            format_data, is_open = integration.format_pull_request_data_to_webhook_request_data(
                repository_data, pull_request_data
            )
            data = integration.parse_pull_request_data(format_data)
        except Exception:
            logger.exception(
                "Failed to parse Pull Request",
                extra={
                    "provider": integration.provider.name,
                    "repository": repository.full_name(),
                    "organization": repository.organization.name,
                    "repository_data": repository_data,
                    "pull_request_data": pull_request_data,
                },
            )
            return False

        if self.pull_request_exists(repository, data.pr_number):
            logger.info(f"Skipping PR#{data.pr_number} for repository '{repository.full_name()}' -  already exists")
            return False

        if not is_open:
            logger.info(f"Skipping PR#{data.pr_number} for repository '{repository.full_name()}' - not open")
            self.create_closed_pull_request(repository, data)
            return False

        logger.info(f"Processing PR#{data.pr_number} for repository '{repository.full_name()}'...")

        return ProcessPullRequestTask().run(data, integration)

    def create_closed_pull_request(self, repository: Repository, pull_request_data: PullRequestData):
        RepositoryPullRequest.objects.create(
            repository=repository,
            pr_number=pull_request_data.pr_number,
            base_commit_sha=pull_request_data.base_sha,
            head_commit_sha=pull_request_data.head_sha,
            is_closed=True,
        )

    def get_organizations(self, organization_id=None):
        qs = Organization.objects.filter(status_check_enabled=True)

        if organization_id:
            qs = qs.filter(id=organization_id)

        return qs.all()

    def get_organization_connections(self, organization: Organization, providers: [str] = None):
        # TODO: this pattern is duplicated in other places, consider refactoring
        queryset = DataProviderConnection.objects.filter(
            organization=organization,
            provider__in=get_git_providers(),
            data__isnull=False,
        )

        if providers is not None:
            queryset = queryset.filter(provider__name__in=providers)

        return queryset.prefetch_related("provider").all()

    def get_repository(self, organization, repository_external_id):
        try:
            return Repository.objects.get(organization=organization, external_id=repository_external_id)
        except Repository.DoesNotExist:
            return None

    def pull_request_exists(self, repository, pr_number):
        return RepositoryPullRequest.objects.filter(
            repository=repository,
            pr_number=pr_number,
        ).exists()

    def validate_providers(self, providers: [str]) -> bool:
        if providers:
            available_providers = {provider.name for provider in get_git_providers()}
            invalid_providers = [provider for provider in providers if provider not in available_providers]

            if invalid_providers:
                logger.error(
                    "Invalid providers provided",
                    extra={
                        "providers": invalid_providers,
                        "available_providers": available_providers,
                    },
                )
                return False

        return True

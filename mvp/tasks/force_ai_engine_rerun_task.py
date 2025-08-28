import logging
import operator
import os
from functools import reduce

from django.db.models import Q
from sentry_sdk import capture_message, push_scope

from compass.integrations.apis import (
    AzureDevOpsApiConfig,
    BitBucketApiConfig,
    GitHubApiConfig,
)
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
    get_git_provider_integration,
)
from mvp.models import (
    DataProviderConnection,
    Organization,
    Repository,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
)
from mvp.tasks import DownloadRepositoriesTask
from mvp.utils import shred_path

logger = logging.getLogger(__name__)


class ForceAiEngineRerunTask:
    def prepare_pull_request_for_re_analysis(self, pull_request):
        """Prepare the pull request for re-analysis by deleting the analysis files and marking the commits as pending.

        Formatted data and integration object are returned to be used by the ProcessPullRequestTask.
        """
        provider = pull_request.repository.provider
        integration_class = get_git_provider_integration(provider)
        integration = integration_class()
        connection = self.get_connection(pull_request.repository.organization, provider)
        if isinstance(integration, AzureDevOpsIntegration):
            config = AzureDevOpsApiConfig(
                base_url=connection.data["base_url"],
                auth_token=connection.data["personal_access_token"],
            )
            integration.init_api(config)
        elif isinstance(integration, BitBucketIntegration):
            config = BitBucketApiConfig(
                workspace=connection.data.get("workspace"),
                access_token=connection.data.get("access_token"),
                refresh_token=connection.data.get("refresh_token"),
            )
            integration.init_api(config, connection)
        elif isinstance(integration, GitHubIntegration):
            installation_id = pull_request.repository.external_data.get("installation_id")
            config = GitHubApiConfig(
                installation_id=installation_id,
            )
            integration.init_api(config)
        else:
            return None, None

        repo_data, pr_data = integration.get_formatted_pull_request_with_repository_data(pull_request)
        format_data, is_open = integration.format_pull_request_data_to_webhook_request_data(repo_data, pr_data)
        data = integration.parse_pull_request_data(format_data)
        if not is_open:
            pull_request.is_closed = True
            pull_request.save()
            return None, None

        repository = pull_request.repository
        commits = self.get_commits_by_sha(
            organization_id=repository.organization.id,
            repository_id=repository.id,
            commit_sha=data.head_sha,
        )
        if not commits.exists():
            with push_scope() as scope:
                scope.set_extra("provider", integration.provider.name)
                scope.set_extra("repository", repository.full_name())
                scope.set_extra("organization", repository.organization.name)
                scope.set_extra("repository_data", repo_data)
                scope.set_extra("pull_request_data", pr_data)
                capture_message(
                    f"No commits found for pull request Id: {pull_request.id}",
                    level="error",
                )
            return None, None

        self.delete_analysis_directories(commits)
        self.delete_analysis_files(commits)
        self.mark_commits_pending(commits)

        return data, integration

    def mark_commits_pending(self, commits):
        return commits.update(status=RepositoryCommitStatusChoices.PENDING)

    def get_organization(self, organization_id):
        try:
            return Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return None

    def get_commits(self, organization_id, repository_id=None, commit_sha=None):
        return (
            self.get_commits_by_sha(organization_id, repository_id, commit_sha)
            if commit_sha
            else self.get_last_commits(organization_id, repository_id)
        ).prefetch_related("repository")

    def get_last_commits(self, organization_id, repository_id=None):
        qs = Repository.objects.filter(organization__id=organization_id)

        if repository_id:
            qs = qs.filter(id=repository_id)

        repositories = qs.values("id", "last_commit_sha")

        conditions = [Q(repository__id=repo["id"], sha=repo["last_commit_sha"]) for repo in repositories]
        return RepositoryCommit.objects.filter(reduce(operator.or_, conditions))

    def get_commits_by_sha(self, organization_id, repository_id, commit_sha):
        qs = RepositoryCommit.objects.filter(
            repository__organization__id=organization_id,
            sha=commit_sha,
        )

        if repository_id:
            qs = qs.filter(repository__id=repository_id)

        return qs.all()

    def delete_analysis_directories(self, commits):
        for commit in commits:
            self.delete_analysis_directory(commit.analysis_folder())

    def delete_analysis_directory(self, path):
        try:
            shred_path(path)
            logger.info(f"Deleted repository from disk: {path}")
        except Exception as error:
            logger.exception(f"Failed to delete repository from disk")

    def delete_analysis_files(self, commits):
        for commit in commits:
            csv_path = commit.analysis_file
            authors_csv_path = csv_path.replace(".csv", ".authors.csv")
            self.delete_disk_file(csv_path)
            self.delete_disk_file(authors_csv_path)

    def delete_disk_file(self, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")

    def redownload_commits(self, commits, organization):
        downloader = DownloadRepositoriesTask()

        connections = downloader.get_connections(organization.id)
        repositories = {}
        for connection in connections:
            for repository_data, integration in downloader.get_connection_repositories(connection):
                key = f"{integration.provider}_{repository_data.id}"
                repositories[key] = (repository_data, integration)

        for commit in commits:
            repository = commit.repository
            key = f"{repository.provider}_{repository.external_id}"
            if key not in repositories:
                logger.warning(
                    f"Can't re-download SHA '{commit.sha}' for repository "
                    f"'{repository.name}' - not found in the connections. "
                    f"Check it was not manually imported."
                )
                continue

            repository_data, integration = repositories[key]

            downloader.download_repository_commit(
                repository_data,
                organization,
                repository,
                commit,
                integration,
                force=True,
            )

    def get_connection(self, organization, provider):
        return DataProviderConnection.objects.filter(
            organization=organization,
            provider=provider,
            data__isnull=False,
        ).first()

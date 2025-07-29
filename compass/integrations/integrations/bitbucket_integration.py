import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import quote_plus

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from compass.integrations.apis import BitBucketApi, BitBucketApiConfig
from compass.integrations.integrations.git_base_integration import (
    GitBaseIntegration,
    GitCommitData,
    GitRepositoryData,
    PullRequestData,
)
from mvp.models import (
    DataProviderConnection,
    DataProviderMemberProjectRecord,
    DataProviderRecord,
    ModuleChoices,
    Repository,
    RepositoryPullRequest,
)

logger = logging.getLogger(__name__)


class BitBucketIntegrationException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class BitBucketPullRequestData(PullRequestData):
    workspace: str


class BitBucketIntegration(GitBaseIntegration):
    DAY_FORMAT = "%Y-%m-%d"

    BASE_BITBUCKET_SITE_URL = "https://bitbucket.org"

    CHECK_RUN_STATUS_IN_PROGRESS = "INPROGRESS"
    CHECK_RUN_CONCLUSION_SUCCESS = "SUCCESSFUL"
    CHECK_RUN_CONCLUSION_FAILURE = "FAILED"
    CHECK_RUN_CONCLUSION_CANCELLED = "STOPPED"
    # Neutral and completed doesn't exist in bitbucket.
    CHECK_RUN_STATUS_COMPLETED = "SUCCESSFUL"
    CHECK_RUN_CONCLUSION_NEUTRAL = "SUCCESSFUL"

    FIELD_COMMIT_COUNT = "bitbucket_commit_count"
    FIELD_FILE_CHANGE_COUNT = "bitbucket_file_change_count"

    # TODO: set to 12 when there's a backwards strategy
    NUM_MONTHS_FETCH_NEW_PROJECT = 3

    WEBHOOK_REQUEST_HEADER_ID = "X-Request-Uuid"
    WEBHOOK_EVENT_KEY = "X-Event-Key"

    WEBHOOK_ACTION_OPENED = "pullrequest:created"
    WEBHOOK_ACTION_CLOSED = "pullrequest:fulfilled"
    WEBHOOK_ACTION_REJECTED = "pullrequest:rejected"
    WEBHOOK_ACTION_SYNCHRONIZE = "pullrequest:updated"

    WEBHOOK_CLOSED_ACTIONS = [
        WEBHOOK_ACTION_CLOSED,
        WEBHOOK_ACTION_REJECTED,
    ]

    PULL_REQUEST_STATE_OPEN = "OPEN"

    def __init__(self):
        super().__init__()
        self._repo_ids_by_workspace = {}

    @property
    def modules(self):
        return [ModuleChoices.PROCESS, ModuleChoices.TEAM]

    def fetch_data(self, connection):
        self.init_connection(connection)
        self.organization = connection.organization

        self.fields = self.get_or_create_fields()

        # TODO: allow users to select workspace(s) and repository(ies)
        logger.info("Retrieving repositories...")
        projects = self.fetch_projects()
        logger.info(f"{len(projects)} repositories found")

        for project in projects:
            self.process_project(project)

        self.update_last_fetched(connection)

    def fetch_projects(self):
        projects = []

        workspaces = self.api.list_user_workspaces(all_pages=True)
        for workspace in workspaces:
            projects.extend(self.fetch_workspace_projects(workspace))

        return projects

    def fetch_workspace_projects(self, workspace):
        projects = []

        workspace_id = workspace["slug"]
        repositories = self.api.list_workspace_repositories(workspace_id, all_pages=True)

        for repo in repositories:
            repo_id = repo["uuid"]
            repo_name = repo["name"]
            project = self.get_or_update_project(self.organization, repo_name, repo_id, repo)

            # Skip empty repositories (we still store them for stats purposes)
            repo_size = project.meta["size"]
            if not repo_size:
                continue

            projects.append(project)

        return projects

    def process_project(self, project):
        repo_name = project.meta["slug"]
        workspace = project.meta["workspace"]["slug"]
        since, until = self.get_since_until(project)

        # Skip since X 23:59:59 until X+1 00:00:00
        if (until - since).total_seconds() <= 1:
            return

        stats_by_day = self.get_stats_by_day(workspace, repo_name, since, until)

        for stats in stats_by_day.values():
            self.record_project_stats(project, stats)

            for developer in stats["developers"].values():
                self.record_developer_stats(project, developer, stats["date"])

    def record_project_stats(self, project, stats):
        DataProviderRecord.objects.create(
            project=project,
            field=self.fields[self.FIELD_COMMIT_COUNT],
            value=stats["commit_count"],
            date_time=stats["date"],
        )
        DataProviderRecord.objects.create(
            project=project,
            field=self.fields[self.FIELD_FILE_CHANGE_COUNT],
            value=stats["file_change_count"],
            date_time=stats["date"],
        )

    def record_developer_stats(self, project, developer, date):
        user = developer["data"].get("user")
        developer_id = user["uuid"] if user else developer["data"]["raw"]
        developer_name = user["display_name"] if user else developer["data"]["raw"].split("<")[0].strip()

        member = self.get_or_update_member(self.organization, developer_name, developer_id, developer["data"])

        DataProviderMemberProjectRecord.objects.create(
            member=member,
            project=project,
            field=self.fields[self.FIELD_COMMIT_COUNT],
            value=developer["commit_count"],
            date_time=date,
        )

    def get_stats_by_day(self, workspace, repo_name, since, until):
        stats_by_day = self.get_commits_by_day(workspace, repo_name, since, until)

        for day, stats in stats_by_day.items():
            stats_by_day[day]["file_change_count"] = self.get_num_files_changed_between_commits(
                workspace, repo_name, stats["first_commit"], stats["last_commit"]
            )

        return stats_by_day

    def get_commits_by_day(self, workspace, repo_name, since, until):
        commits, links = self.api.list_commits(workspace, repo_name, return_links=True)

        stats = {}
        while commits:
            for commit in commits:
                date = datetime.strptime(commit["date"], BitBucketApi.DATE_FORMAT)

                # Bitbucket API returns commits in reverse chronological order,
                # and there's no way to filter by date
                if date > until:
                    continue

                if date <= since:
                    return stats

                day = date.strftime(self.DAY_FORMAT)

                if day not in stats:
                    stats[day] = {
                        "date": date,
                        "commit_count": 1,
                        "first_commit": commit["hash"],
                        "last_commit": commit["hash"],
                        "developers": {},
                    }
                else:
                    stats[day]["commit_count"] += 1
                    stats[day]["first_commit"] = commit["hash"]

                developer = commit["author"]
                developer_name = developer["raw"]
                if developer_name not in stats[day]["developers"]:
                    stats[day]["developers"][developer_name] = {
                        "data": developer,
                        "commit_count": 1,
                    }

            if "next" not in links:
                break

            commits, links = self.api.parse_response(self.api.request(links["next"]["url"]))

        return stats

    def filter_commits(self, commits, since, until):
        filtered_commits = []
        for commit in commits:
            commit_date = datetime.strptime(commit["date"], BitBucketApi.DATE_FORMAT)
            if since <= commit_date <= until:
                filtered_commits.append(commit)

        return (filtered_commits, len(filtered_commits) != len(commits))

    def get_num_files_changed_between_commits(self, workspace, repo_name, base, head):
        files = self.api.compare_commits(workspace, repo_name, base, head)

        return len(files)

    def get_or_create_fields(self):
        fields = [
            self.FIELD_COMMIT_COUNT,
            self.FIELD_FILE_CHANGE_COUNT,
        ]
        return {field: self.get_or_create_field(field) for field in fields}

    @staticmethod
    def get_workspace_connection(workspace_id):
        return DataProviderConnection.objects.filter(
            provider=BitBucketIntegration().provider,
            data__workspace=workspace_id,
        ).last()

    @staticmethod
    def get_connection_credentials(connection: DataProviderConnection | None):
        if not connection:
            return None, None

        return connection.data.get("access_token"), connection.data.get("refresh_token")

    @staticmethod
    def get_workspace_credentials(workspace_id):
        connection = BitBucketIntegration.get_workspace_connection(workspace_id)

        return BitBucketIntegration.get_connection_credentials(connection)

    def init_connection(self, connection):
        config = BitBucketApiConfig(
            workspace=connection.data["workspace"],
            access_token=connection.data["access_token"],
            refresh_token=connection.data["refresh_token"],
        )
        self.init_api(config, connection)

    def init_api(self, config: BitBucketApiConfig, connection: DataProviderConnection):
        self.api = BitBucketApi(config)
        try:
            access_token, refresh_token = self.api.refresh_tokens()
        except requests.exceptions.RequestException as e:
            if self._is_invalid_refresh_token_error(e.response):
                logger.warning(
                    "Invalid refresh token detected, disconnecting...",
                    extra={"organization": connection.organization, "provider": connection.provider.name},
                )
                self.disconnect(connection)
            raise

        self.update_connection_tokens(connection, access_token, refresh_token)

    def _is_invalid_refresh_token_error(self, response) -> bool:
        if response is not None and response.status_code == 400:
            text = getattr(response, "text", None)
            if not text:
                return False
            try:
                error_data = json.loads(text)
                return error_data.get("error_description") == "Invalid refresh_token"
            except (ValueError, TypeError):
                pass
        return False

    @staticmethod
    def update_connection_tokens(
        connection: DataProviderConnection,
        access_token: str,
        refresh_token: str,
    ):
        connection.data["access_token"] = access_token
        connection.data["refresh_token"] = refresh_token
        connection.save()

    def parse_pull_request_data(self, request_data: dict):
        repository = request_data["repository"]
        pull_request = request_data["pullrequest"]

        pr_source = pull_request.get("source")
        pr_destination = pull_request.get("destination")
        pr_updated_on = pull_request.get("updated_on", timezone.now().isoformat())

        return BitBucketPullRequestData(
            workspace=repository["workspace"]["slug"],
            repo_external_id=repository["uuid"],
            action=request_data["action"],
            repo_owner=repository["workspace"]["slug"],
            repo_name=repository["name"],
            repo_full_name=repository["full_name"],
            head_sha=pr_source["commit"]["hash"] if pr_source and pr_source.get("commit") else "",
            base_sha=pr_destination["commit"]["hash"] if pr_destination and pr_destination.get("commit") else "",
            pr_number=pull_request["id"],
            updated_at=datetime.fromisoformat(pr_updated_on),
            merged_at=(datetime.fromisoformat(pr_updated_on) if pull_request.get("merge_commit") else None),
            merge_commit_sha=(pull_request["merge_commit"]["hash"] if pull_request.get("merge_commit") else None),
        )

    def format_pull_request_data_to_webhook_request_data(
        self, repository_data: GitRepositoryData, pull_request_data
    ) -> Tuple[dict, bool]:
        data = {
            "action": self.WEBHOOK_ACTION_OPENED,
            "repository": repository_data.raw_data,
            "pullrequest": pull_request_data,
        }
        is_open = pull_request_data["state"] == self.PULL_REQUEST_STATE_OPEN

        return data, is_open

    def create_check_run(
        self,
        data: BitBucketPullRequestData,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        old_external_data: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        if old_external_data and "commentId" in old_external_data:
            self.api.delete_comment(
                repo_full_name=data.repo_full_name,
                pr_number=data.pr_number,
                comment_id=old_external_data["commentId"],
            )

        if not details_url:
            details_url = self.get_details_url(
                external_id=data.repo_external_id,
                pr_number=data.pr_number,
            )

        response = self.api.create_check_run(
            data.repo_full_name,
            data.head_sha,
            conclusion=conclusion or self.CHECK_RUN_STATUS_IN_PROGRESS,
            details_url=details_url,
            output=output,
        )
        if output:
            comment_response = self.api.post_pull_request_comment(
                repo_full_name=data.repo_full_name,
                pr_number=data.pr_number,
                comment=output,
            )
            external_data = {"commentId": comment_response["id"]}
        else:
            external_data = {}

        return response["key"], external_data

    def update_check_run(
        self,
        data: BitBucketPullRequestData,
        check_run_id,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        old_external_data: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        if old_external_data and "commentId" in old_external_data:
            self.api.delete_comment(
                repo_full_name=data.repo_full_name,
                pr_number=data.pr_number,
                comment_id=old_external_data["commentId"],
            )

        if not details_url:
            details_url = self.get_details_url(
                external_id=data.repo_external_id,
                pr_number=data.pr_number,
            )

        response = self.api.update_check_run(
            data.repo_full_name,
            head_sha=data.head_sha,
            conclusion=conclusion or self.CHECK_RUN_STATUS_IN_PROGRESS,
            check_run_id=check_run_id,
            output=output,
            details_url=details_url,
        )
        if output:
            comment_response = self.api.post_pull_request_comment(
                repo_full_name=data.repo_full_name,
                pr_number=data.pr_number,
                comment=output,
            )
            external_data = {"commentId": comment_response["id"]}
        else:
            external_data = {}

        return response["key"], external_data

    def complete_check_run(
        self,
        data: BitBucketPullRequestData,
        check_run_id: int,
        conclusion: str,
        output: dict,
        details_url: str,
        old_external_data: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        if old_external_data and "commentId" in old_external_data:
            self.api.delete_comment(
                repo_full_name=data.repo_full_name,
                pr_number=data.pr_number,
                comment_id=old_external_data["commentId"],
            )

        if not details_url:
            details_url = self.get_details_url(
                external_id=data.repo_external_id,
                pr_number=data.pr_number,
            )

        response = self.api.update_check_run(
            data.repo_full_name,
            head_sha=data.head_sha,
            conclusion=conclusion,
            check_run_id=check_run_id,
            output=output,
            details_url=details_url,
        )
        if output:
            comment_response = self.api.post_pull_request_comment(
                repo_full_name=data.repo_full_name,
                pr_number=data.pr_number,
                comment=output,
            )
            external_data = {"commentId": comment_response["id"]}
        else:
            external_data = {}

        return response["key"], external_data

    @staticmethod
    def get_details_url(external_id, pr_number):
        """
        BitBucket status checks require a URL.

        If no URL provided this is used.
        """
        pull_path = reverse(
            "pull_request_scan",
            kwargs={
                "external_id": external_id,
                "pr_number": pr_number,
            },
        )
        return f"{settings.SITE_DOMAIN}{pull_path}"

    def get_pull_request_commits(self, data: BitBucketPullRequestData):
        commits = self.api.get_pull_request_commits(
            repo_owner=data.repo_owner,
            repo_name=data.repo_name,
            pr_number=data.pr_number,
        )
        return [commit["hash"] for commit in commits]

    def get_pull_request_files(self, data: BitBucketPullRequestData):
        return self.api.get_pull_request_files(
            repo_full_name=data.repo_full_name,
            pull_request_number=data.pr_number,
        )

    def is_empty_repository(self, repository: GitRepositoryData):
        return not repository.raw_data["size"]

    def get_repository_last_commit(self, repository: GitRepositoryData) -> Optional[GitCommitData]:
        commit = self.api.get_last_commit(
            workspace_id=repository.owner,
            repository_slug=repository.name,
        )
        return GitCommitData(
            sha=commit["hash"],
            date=commit["date"],
            raw_data=commit,
        )

    def get_repository_commit_by_date(self, repository: GitRepositoryData, date: datetime) -> Optional[GitCommitData]:
        commits = self.api.list_commits(
            repository.owner,
            repository.name,
            all_pages=True,
        )

        if not commits:
            return None

        for commit in commits:
            parsed_date = datetime.fromisoformat(commit["date"])
            if parsed_date.year == date.year and parsed_date.month == date.month and parsed_date.day == date.day:
                return GitCommitData(
                    sha=commit["hash"],
                    date=parsed_date,
                    raw_data=commit,
                )

        return None

    def get_repository_git_url(self, repository: GitRepositoryData) -> str | None:
        return self.api.get_repo_url(owner=repository.owner, repo_name=repository.name)

    def is_repository_connected(self, repository: Repository) -> bool:
        workspace = repository.owner

        access_token, refresh_token = self.get_workspace_credentials(workspace)

        if not access_token or not refresh_token:
            return False

        repository_ids = self.get_workspace_repository_ids(workspace, access_token, refresh_token)
        return repository.external_id in repository_ids

    def get_workspace_repository_ids(
        self,
        workspace: str,
        access_token: str,
        refresh_token: str,
    ):
        self.load_workspace_repository_ids(workspace, access_token, refresh_token)
        return self._repo_ids_by_workspace.get(workspace, [])

    def load_workspace_repository_ids(
        self,
        workspace: str,
        access_token: str,
        refresh_token: str,
    ):
        if workspace not in self._repo_ids_by_workspace:
            try:
                self.init_api(
                    BitBucketApiConfig(
                        workspace=workspace,
                        access_token=access_token,
                        refresh_token=refresh_token,
                    ),
                    self.get_workspace_connection(workspace),
                )

                response = self.api.list_repos(workspace)
                repositories = response.get("values", [])

                self._repo_ids_by_workspace[workspace] = [str(repo.get("uuid")) for repo in repositories]

            except Exception as error:
                self._repo_ids_by_workspace[workspace] = []

    def get_repository_pull_requests(
        self,
        repository: GitRepositoryData,
        since: Optional[datetime] = None,  # Not used in BitBucket
        until: Optional[datetime] = None,  # Not used in BitBucket
        state: Optional[str] = None,
    ) -> list[dict]:
        return self.api.get_repository_pull_requests(
            repo_owner=repository.owner,
            repo_name=repository.name,
            state=state,
        )

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return (
            connection.data
            and connection.data.get("workspace")
            and connection.data.get("access_token")
            and connection.data.get("refresh_token")
        )

    @classmethod
    def get_connected_repositories_with_integration(
        cls,
        connection: DataProviderConnection,
    ):
        integration = BitBucketIntegration()
        workspace = connection.data.get("workspace")
        integration.init_api(
            BitBucketApiConfig(
                workspace=connection.data.get("workspace"),
                access_token=connection.data.get("access_token"),
                refresh_token=connection.data.get("refresh_token"),
            ),
            connection,
        )
        repositories = integration.api.list_repos_for_workspace(workspace)

        return [
            (
                GitRepositoryData(
                    id=repo["uuid"],
                    name=repo["name"],
                    owner=repo["workspace"]["slug"],
                    raw_data=repo,
                    store_data={
                        "workspace": integration.api.workspace,
                    },
                ),
                integration,
            )
            for repo in repositories
        ]

    @staticmethod
    def disconnect(connection: DataProviderConnection):
        # BitBucket does not offer a way to revoke installed apps via API, only available in their UI.
        # Doing this to invalidate access/refresh tokens and disconnect webhooks if connection is still valid
        if not connection or not connection.data:
            logger.warning("No connection or no data. cannot disconnect")
            return
        access_token = connection.data.get("access_token")
        refresh_token = connection.data.get("refresh_token")
        if not refresh_token or not access_token:
            return

        config = BitBucketApiConfig(
            workspace=connection.data.get("workspace"),
            access_token=access_token,
            refresh_token=refresh_token,
        )
        api = BitBucketApi(config)

        try:
            # if the connection is still valid, delete webhooks
            api.delete_webhooks_for_workspace(connection.data["workspace"])
        except requests.exceptions.RequestException:
            # This means that the access was revoked already and the app was probably uninstalled
            logger.warning(
                "Failed to delete webhooks for workspace",
                extra={"workspace": connection.data["workspace"], "organization": connection.organization.name},
            )

        connection.data["disconnected_access_token"] = access_token
        connection.data["access_token"] = None
        connection.data["disconnected_refresh_token"] = refresh_token
        connection.data["refresh_token"] = None
        connection.save()

    @classmethod
    def get_repository_url(cls, repository: Repository) -> str:
        return f"{cls.BASE_BITBUCKET_SITE_URL}/{repository.full_name()}"

    @staticmethod
    def get_commit_url(repository: Repository, short_commit_hash: str) -> Optional[str]:
        repository_url = BitBucketIntegration.get_repository_url(repository)
        full_commit_hash = BitBucketIntegration.get_full_commit_hash(repository, short_commit_hash)
        if full_commit_hash:
            return f"{repository_url}/commits/{full_commit_hash}"
        return None

    @staticmethod
    def get_file_url(
        repository: Repository,
        file_name: str,
        commit_hash: str = None,
        branch_name: str = None,
    ) -> Optional[str]:
        repository_url = BitBucketIntegration.get_repository_url(repository)
        if not repository_url:
            return None

        encoded_filename = quote_plus(file_name)

        if commit_hash:
            return f"{repository_url}/diff/{encoded_filename}?diff2={commit_hash}"
        else:
            default_branch = branch_name or repository.default_branch_name
            if not default_branch:
                return None
            return f"{repository_url}/src/{default_branch}/{encoded_filename}"

    @classmethod
    def get_pull_request_url(cls, pull_request: RepositoryPullRequest) -> str:
        return (
            f"{cls.BASE_BITBUCKET_SITE_URL}/{pull_request.repository.full_name()}"
            f"/pull-requests/{pull_request.pr_number}"
        )

    def get_formatted_pull_request_with_repository_data(
        self,
        pull_request: RepositoryPullRequest,
    ) -> Tuple[GitRepositoryData, Dict]:
        repo_full_name = pull_request.repository.full_name()
        repo_data = self.api.get_repository(
            repo_full_name=repo_full_name,
        )
        formatted_repo_data = GitRepositoryData(
            id=repo_data["uuid"],
            name=repo_data["name"],
            owner=repo_data["workspace"]["slug"],
            raw_data=repo_data,
            store_data=pull_request.repository.external_data,
        )
        pr_data = self.api.get_pull_request(
            repo_full_name=repo_full_name,
            pr_number=pull_request.pr_number,
        )
        return formatted_repo_data, pr_data

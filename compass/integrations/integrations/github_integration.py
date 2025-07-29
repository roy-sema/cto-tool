import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import quote_plus

from django.utils import timezone
from sentry_sdk import capture_message, push_scope

from compass.integrations.apis import (
    GitHubApi,
    GitHubApiConfig,
    GitHubInstallationDoesNotExist,
)
from compass.integrations.integrations import (
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


@dataclass(frozen=True, kw_only=True)
class GitHubPullRequestData(PullRequestData):
    installation_id: str


class GitHubIntegration(GitBaseIntegration):
    FIELD_COMMIT_COUNT = "github_commit_count"
    FIELD_FILE_CHANGE_COUNT = "github_file_change_count"

    # TODO: set to 12 when there's a backwards strategy
    NUM_MONTHS_FETCH_NEW_PROJECT = 3

    WEBHOOK_REQUEST_HEADER_ID = "X-Github-Delivery"

    def __init__(self):
        super().__init__()
        self.fields = None
        self.organization = None
        self._repo_ids_by_installation = {}

    @property
    def modules(self):
        return [ModuleChoices.PROCESS, ModuleChoices.TEAM]

    def fetch_data(self, connection):
        self.organization = connection.organization

        self.fields = self.get_or_create_fields()

        for installation_id in connection.data["installation_ids"]:
            try:
                self.fetch_installation_data(installation_id)
            except GitHubInstallationDoesNotExist:
                logger.info(
                    f"GitHub installation {installation_id} does not exist for {self.organization}. User probably disconnected it from GitHub."
                )
                GitHubIntegration.update_disconnected_installation_ids(connection, [installation_id])

        self.update_last_fetched(connection)

    def fetch_installation_data(self, installation_id):
        self.api = GitHubApi(GitHubApiConfig(installation_id))

        repositories = self.api.list_repos(all_pages=True)

        logger.info("Retrieving repositories...")
        projects = self.fetch_projects(repositories)
        logger.info(f"{len(projects)} repositories found")

        for project in projects:
            self.process_project(project)

    def fetch_projects(self, repositories):
        projects = []
        for repo in repositories:
            repo_id = repo["id"]
            repo_name = repo["name"]
            project = self.get_or_update_project(self.organization, repo_name, repo_id, repo)

            # Skip empty repositories (we still store them for stats purposes)
            repo_size = project.meta["size"]
            if not repo_size:
                continue

            projects.append(project)

        return projects

    def process_project(self, project):
        repo_name = project.meta["name"]
        repo_owner = project.meta["owner"]["login"]
        default_branch = project.meta["default_branch"]
        since, until = self.get_since_until(project)

        # Skip since X 23:59:59 until X+1 00:00:00
        if (until - since).total_seconds() <= 1:
            return

        since_until_days = self.get_since_until_days(since, until)
        logger.info(f"Retrieving commit activity for repository '{repo_name}' since {since} until {until}")

        for since, until in since_until_days:
            date = until - timedelta(seconds=1)
            commit_count, file_change_count, developers = self.get_stats(
                repo_owner, repo_name, default_branch, since, until
            )

            self.record_project_stats(project, commit_count, file_change_count, date)

            for developer in developers.values():
                self.record_developer_stats(project, developer, date)

    def record_project_stats(self, project, commit_count, file_change_count, date):
        DataProviderRecord.objects.create(
            project=project,
            field=self.fields[self.FIELD_COMMIT_COUNT],
            value=commit_count,
            date_time=date,
        )
        DataProviderRecord.objects.create(
            project=project,
            field=self.fields[self.FIELD_FILE_CHANGE_COUNT],
            value=file_change_count,
            date_time=date,
        )

    def record_developer_stats(self, project, developer, date):
        developer_id = developer["data"]["id"]
        developer_name = developer["data"]["login"]
        member = self.get_or_update_member(self.organization, developer_name, developer_id, developer["data"])

        DataProviderMemberProjectRecord.objects.create(
            member=member,
            project=project,
            field=self.fields[self.FIELD_COMMIT_COUNT],
            value=developer["commit_count"],
            date_time=date,
        )

    def get_stats(self, owner_name, repo_name, branch, since, until):
        num_commits, first_commit, last_commit, developers = self.get_commits(
            owner_name, repo_name, branch, since, until
        )

        files_changed = (
            self.get_num_files_changed_between_commits(owner_name, repo_name, first_commit, last_commit)
            if num_commits
            else 0
        )

        return num_commits, files_changed, developers

    def get_commits(self, owner_name, repo_name, branch, since, until):
        commits = self.api.list_commits(owner_name, repo_name, branch, since, until, all_pages=True)

        num_commits = 0
        last_commit = None
        first_commit = None
        developers = {}

        for commit in commits:
            author = commit["author"] if commit["author"] else commit["committer"]
            if not author or author.get("type") == "Bot":
                continue

            num_commits += 1

            # Commits are returned in reverse chronological order
            if not last_commit:
                last_commit = commit["sha"]

            first_commit = commit["sha"]

            developer_id = author["id"]
            if developer_id not in developers:
                developers[developer_id] = {
                    "data": author,
                    "commit_count": 1,
                }
            else:
                developers[developer_id]["commit_count"] += 1

        return num_commits, first_commit, last_commit, developers

    def get_num_files_changed_between_commits(self, owner_name, repo_name, base, head):
        comparison = self.api.compare_commits(owner_name, repo_name, base, head)

        return len(comparison) if comparison else 0

    def get_since_until_days(self, since, until):
        days = []

        while until > since:
            since_day = max([until - timedelta(days=1), since])
            days.insert(0, (since_day, until))
            until = since_day

        return days

    def get_or_create_fields(self):
        fields = [
            self.FIELD_COMMIT_COUNT,
            self.FIELD_FILE_CHANGE_COUNT,
        ]
        return {field: self.get_or_create_field(field) for field in fields}

    def init_api(self, config: GitHubApiConfig):
        self.api = GitHubApi(config)

    def parse_pull_request_data(self, request_data: dict) -> GitHubPullRequestData:
        repository = request_data["repository"]
        pull_request = request_data["pull_request"]

        return GitHubPullRequestData(
            action=request_data["action"],
            installation_id=request_data["installation"]["id"],
            repo_external_id=repository["id"],
            repo_owner=repository["owner"]["login"],
            repo_name=repository["name"],
            repo_full_name=repository["full_name"],
            head_sha=pull_request["head"]["sha"],
            base_sha=pull_request["base"]["sha"],
            pr_number=pull_request["number"],
            updated_at=self.parse_date(
                pull_request["head"]["repo"]["updated_at"]
                if pull_request["head"]["repo"]
                else pull_request["updated_at"]
            ),
            merged_at=(self.parse_date(pull_request["merged_at"]) if pull_request.get("merged_at") else None),
            merge_commit_sha=pull_request["merge_commit_sha"],
        )

    def parse_date(self, date_time):
        return timezone.make_aware(datetime.strptime(date_time, GitHubApi.DATE_FORMAT))

    def format_pull_request_data_to_webhook_request_data(
        self,
        repository_data: GitRepositoryData,
        pull_request_data,
    ) -> Tuple[dict, bool]:
        data = {
            "action": self.WEBHOOK_ACTION_OPENED,
            "installation": {
                "id": repository_data.store_data["installation_id"],
            },
            "repository": repository_data.raw_data,
            "pull_request": pull_request_data,
        }

        is_open = pull_request_data["state"] == "open"

        return data, is_open

    def create_check_run(
        self,
        data: GitHubPullRequestData,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        response = self.api.create_check_run(
            data.repo_full_name,
            data.head_sha,
            status=status or self.CHECK_RUN_STATUS_IN_PROGRESS,
            conclusion=conclusion,
            details_url=details_url,
            output=output,
        )
        return response["id"], {}

    def update_check_run(
        self,
        data: GitHubPullRequestData,
        check_run_id,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        response = self.api.update_check_run(
            data.repo_full_name,
            status=status or self.CHECK_RUN_STATUS_IN_PROGRESS,
            check_run_id=check_run_id,
            conclusion=conclusion,
            output=output,
            details_url=details_url,
        )
        return response["id"], {}

    def complete_check_run(
        self,
        data: GitHubPullRequestData,
        check_run_id: int,
        conclusion: str,
        output: dict,
        details_url: str,
        **kwargs,
    ) -> Tuple[int, dict]:
        response = self.api.update_check_run(
            data.repo_full_name,
            status=self.CHECK_RUN_STATUS_COMPLETED,
            check_run_id=check_run_id,
            conclusion=conclusion,
            output=output,
            details_url=details_url,
        )

        return response["id"], {}

    def get_pull_request_commits(self, data: GitHubPullRequestData):
        shas = {data.head_sha}

        commits = self.api.get_pull_request_commits(data.repo_full_name, data.pr_number, all_pages=True)

        shas.update(commit["sha"] for commit in commits)
        shas.discard(data.base_sha)

        return list(shas)

    def get_pull_request_files(self, data: GitHubPullRequestData):
        return self.api.get_pull_request_files(data.repo_full_name, data.pr_number, all_pages=True)

    def is_empty_repository(self, repository: GitRepositoryData):
        return not repository.raw_data["size"]

    def get_repository_last_commit(self, repository: GitRepositoryData) -> Optional[GitCommitData]:
        default_branch = repository.raw_data["default_branch"]
        commits = self.api.list_commits(
            repository.owner,
            repository.name,
            default_branch,
            per_page=1,
            return_links=False,
        )

        if not commits:
            return None

        return GitCommitData(
            sha=commits[0]["sha"],
            date=self.format_commit_date(commits[0]),
            raw_data=commits[0],
        )

    def get_repository_commit_by_date(self, repository: GitRepositoryData, date: datetime) -> Optional[GitCommitData]:
        # commits are sorted by date in descending order
        until = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        default_branch = repository.raw_data["default_branch"]
        commits = self.api.list_commits(
            repository.owner,
            repository.name,
            default_branch,
            per_page=1,
            return_links=False,
            until=until,
        )

        if not commits:
            return None

        return GitCommitData(
            sha=commits[0]["sha"],
            date=self.format_commit_date(commits[0]),
            raw_data=commits[0],
        )

    def get_repository_git_url(self, repository: GitRepositoryData) -> str:
        return self.api.get_repo_url(repository.owner, repository.name)

    def is_repository_connected(self, repository: Repository) -> bool:
        installation_id = repository.external_data.get("installation_id")
        if not installation_id:
            return False

        repository_ids = self.get_installation_repository_ids(installation_id)
        return repository.external_id in repository_ids

    def get_installation_repository_ids(self, installation_id):
        self.load_installation_repository_ids(installation_id)
        return self._repo_ids_by_installation[installation_id]

    def load_installation_repository_ids(self, installation_id):
        if installation_id not in self._repo_ids_by_installation:
            try:
                self.init_api(GitHubApiConfig(installation_id))
                repositories = self.api.list_repos(all_pages=True)
                self._repo_ids_by_installation[installation_id] = [str(repo["id"]) for repo in repositories]
            except GitHubInstallationDoesNotExist:
                self._repo_ids_by_installation[installation_id] = []

    def get_repository_pull_requests(
        self,
        repository: GitRepositoryData,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        state: Optional[str] = None,
    ) -> list[dict]:
        repo_full_name = f"{repository.owner}/{repository.name}"
        return self.api.get_repository_pull_requests(
            repo_full_name, since=since, until=until, state=state, all_pages=True
        )

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return connection.data and connection.data.get("installation_ids")

    @staticmethod
    def get_connected_repositories_with_integration(connection: DataProviderConnection):
        repositories = []
        for installation_id in connection.data["installation_ids"]:
            try:
                repositories.extend(GitHubIntegration.get_connected_repository_with_integration(installation_id))
            except GitHubInstallationDoesNotExist:
                logger.warning(
                    f"GitHub installation {installation_id} does not exist. User probably disconnected it from GitHub."
                )
                with push_scope() as scope:
                    scope.set_extra("installation_id", installation_id)
                    scope.set_extra("organization", connection.organization.name)
                    capture_message("GitHub installation does not exist. User probably disconnected it from GitHub.")

                    GitHubIntegration.update_disconnected_installation_ids(connection, [installation_id])

        return repositories

    @staticmethod
    def get_connected_repository_with_integration(installation_id):
        integration = GitHubIntegration()
        integration.init_api(GitHubApiConfig(installation_id))

        repos = integration.api.list_repos(all_pages=True)
        return [
            (
                GitRepositoryData(
                    id=str(repo["id"]),
                    name=repo["name"],
                    owner=repo["owner"]["login"],
                    raw_data=repo,
                    store_data={"installation_id": installation_id},
                ),
                integration,
            )
            for repo in repos
        ]

    def get_formatted_pull_request_with_repository_data(self, pull_request):
        repo_response = self.api.get_repository(
            repository_full_name=pull_request.repository.full_name(),
        )
        repo_data = repo_response.json()
        formatted_repo_data = GitRepositoryData(
            id=str(repo_data["id"]),
            name=repo_data["name"],
            owner=repo_data["owner"]["login"],
            raw_data=repo_data,
            store_data=pull_request.repository.external_data,
        )
        pr_response = self.api.get_pull_request(
            repository_full_name=pull_request.repository.full_name(),
            pull_request_number=pull_request.pr_number,
        )
        return formatted_repo_data, pr_response.json()

    @staticmethod
    def disconnect(connection: DataProviderConnection):
        installation_ids = connection.data.get("installation_ids", None)
        if not installation_ids:
            logger.warning("No installation_ids, cannot disconnect")
            return False

        for installation_id in installation_ids:
            try:
                GitHubApi(GitHubApiConfig(installation_id)).delete_installation()
            except GitHubInstallationDoesNotExist:
                logger.info(f"Installation {installation_id} already deleted")

        GitHubIntegration.update_disconnected_installation_ids(connection, installation_ids)
        return True

    @staticmethod
    def update_disconnected_installation_ids(connection: DataProviderConnection, installation_ids):
        connected = set(connection.data.get("installation_ids", []))
        disconnected = set(connection.data.get("disconnected_installation_ids", []))

        for installation_id in installation_ids:
            if installation_id in connected:
                connected.remove(installation_id)
            disconnected.add(installation_id)

        connection.data["installation_ids"] = list(connected)
        connection.data["disconnected_installation_ids"] = list(disconnected)

        connection.save()

    @staticmethod
    def get_repository_url(repository: Repository) -> str:
        return f"https://github.com/{repository.full_name()}"

    @staticmethod
    def get_commit_url(repository: Repository, short_commit_hash: str) -> str:
        repository_url = GitHubIntegration.get_repository_url(repository)
        return f"{repository_url}/commit/{short_commit_hash}"

    @staticmethod
    def get_file_url(
        repository: Repository,
        file_name: str,
        commit_hash: str = None,
        branch_name: str = None,
    ) -> Optional[str]:
        repository_url = GitHubIntegration.get_repository_url(repository)
        if not repository_url:
            return None

        encoded_filename = quote_plus(file_name)

        if commit_hash:
            return f"{repository_url}/blob/{commit_hash}/{encoded_filename}"
        else:
            default_branch = branch_name or repository.default_branch_name
            if not default_branch:
                return None
            return f"{repository_url}/blob/{default_branch}/{encoded_filename}"

    @staticmethod
    def get_pull_request_url(pull_request: RepositoryPullRequest) -> str:
        return f"https://github.com/{pull_request.repository.full_name()}/pull/{pull_request.pr_number}"

    @staticmethod
    def format_commit_date(commit):
        if "commit" in commit and "author" in commit["commit"] and "date" in commit["commit"]["author"]:
            return timezone.make_aware(datetime.strptime(commit["commit"]["author"]["date"], GitHubApi.DATE_FORMAT))

        return datetime.utcnow().date()

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from urllib.parse import quote_plus

from azure.devops.exceptions import AzureDevOpsAuthenticationError
from msrest import Serializer
from sentry_sdk import capture_message, push_scope

from compass.integrations.apis import AzureDevOpsApi, AzureDevOpsApiConfig
from compass.integrations.apis.azure_devops_api import CommentThreadStatus
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
    Organization,
    Repository,
    RepositoryPullRequest,
)
from mvp.utils import retry_on_exceptions

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsPullRequestData(PullRequestData):
    base_url: str
    project_id: str


def find_missing_pr_ids(pr_ids):
    full_range = set(range(min(pr_ids), max(pr_ids) + 1))
    missing_numbers = full_range - set(pr_ids)
    return sorted(missing_numbers)


class AzureDevOpsIntegration(GitBaseIntegration):
    FIELD_COMMIT_COUNT = "azure_devops_commit_count"
    FIELD_FILE_CHANGE_COUNT = "azure_devops_file_change_count"

    FILE_STATUS_MAP = {
        "add": "added",
        "edit": "modified",
        "delete": "removed",
    }

    # TODO: set to 12 when there's a backwards strategy
    NUM_MONTHS_FETCH_NEW_PROJECT = 3

    WEBHOOK_ACTION_OPENED = "git.pullrequest.created"
    # NOTE: Azure DevOps use "updated" for many things, we must parse the data to know what happened
    WEBHOOK_ACTION_SYNCHRONIZE = "git.pullrequest.updated"
    WEBHOOK_ACTION_IGNORE = "ignore"

    WEBHOOK_MESSAGE_REOPENED = "reactivated"
    WEBHOOK_MESSAGE_UPDATED = "updated the source branch"

    WEBHOOK_REQUEST_HEADER_ID = "Request-Id"

    WEBHOOK_RESOURCE_STATUS_ABANDONED = "abandoned"
    WEBHOOK_RESOURCE_STATUS_COMPLETED = "completed"

    def __init__(self):
        super().__init__()
        self.fields = None
        self.organization = None
        self._repo_ids_by_base_url = {}

    @property
    def modules(self):
        return [ModuleChoices.PROCESS, ModuleChoices.TEAM]

    def fetch_data(self, connection):
        self.init_api(
            AzureDevOpsApiConfig(
                base_url=connection.data.get("base_url"),
                auth_token=connection.data.get("personal_access_token"),
            )
        )

        self.organization = connection.organization
        self.fields = self.get_or_create_fields()

        # TODO: allow users to select project(s) and repository(ies)
        logger.info("Retrieving repositories...")
        projects = self.fetch_projects()
        logger.info(f"{len(projects)} repositories found")

        for project in projects:
            self.process_project(project)

        self.update_last_fetched(connection)

    def fetch_projects(self):
        """
        Terminology is confusing here, let's clarify.

        Azure DevOps groups "repositories" into "projects".

        Sema fetches repositories and stores them as DataProviderProjects.

        The reason for that is that non-git providers have no concept of "repository".
        """
        projects = []

        repositories = self.api.list_repos()
        for repo in repositories:
            project = self.get_or_update_project(self.organization, repo.name, repo.id, repo.as_dict())

            # Skip empty repositories (we still store them for stats purposes)
            repo_size = repo.size
            if not repo_size:
                continue

            projects.append(project)

        return projects

    def process_project(self, project):
        repo_id = project.external_id
        repo_name = project.name
        project_name = project.meta["project"]["name"]
        since, until = self.get_since_until(project)

        # Skip since X 23:59:59 until X+1 00:00:00
        if (until - since).total_seconds() <= 1:
            return

        since_until_days = self.get_since_until_days(since, until)
        logger.info(f"Retrieving commit activity for repository '{repo_name}' since {since} until {until}")

        for since, until in since_until_days:
            date = until - timedelta(seconds=1)
            commit_count, file_change_count, developers = self.get_stats(project_name, repo_id, since, until)

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
        developer_id = developer["data"].get("email")
        developer_name = developer["data"]["name"]
        member = self.get_or_update_member(self.organization, developer_name, developer_id, developer["data"])

        DataProviderMemberProjectRecord.objects.create(
            member=member,
            project=project,
            field=self.fields[self.FIELD_COMMIT_COUNT],
            value=developer["commit_count"],
            date_time=date,
        )

    def get_stats(self, project_name, repo_id, since, until):
        num_commits, first_commit, last_commit, developers = self.get_commits(project_name, repo_id, since, until)

        files_changed = (
            self.get_num_files_changed_between_commits(repo_id, first_commit, last_commit) if num_commits else 0
        )

        return num_commits, files_changed, developers

    def get_commits(self, project_name, repo_id, since, until):
        from_date = Serializer().query("to_date", since, "iso-8601")
        to_date = Serializer().query("to_date", until, "iso-8601")
        commits = self.api.list_commits(repo_id, project_name, from_date, to_date)

        num_commits = 0
        last_commit = None
        first_commit = None
        developers = {}

        for commit in commits:
            author = commit.author
            if not author:
                continue

            num_commits += 1

            # Commits are returned in reverse chronological order
            if not last_commit:
                last_commit = commit.commit_id

            first_commit = commit.commit_id

            developer_email = author.email

            # email might be empty, using composite key
            key = developer_email, author.name
            if key not in developers:
                developers[key] = {
                    "data": author.as_dict(),
                    "commit_count": 1,
                }
            else:
                developers[key]["commit_count"] += 1

        return num_commits, first_commit, last_commit, developers

    def get_num_files_changed_between_commits(self, repo_id, base, head):
        files = self.api.get_diff_files(repo_id, base, head)

        return len(files) if files else 0

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

    # TODO: this is needed for downloader, but we should probably pass integration instead. Ignore for now
    def init_api(self, config: AzureDevOpsApiConfig):
        self.api = AzureDevOpsApi(config)

    def parse_pull_request_data(self, request_data: dict) -> AzureDevOpsPullRequestData:
        resource = request_data["resource"]
        repository = resource["repository"]

        action = self.parse_pull_request_action(request_data)
        is_merged = (
            action == self.WEBHOOK_ACTION_CLOSED and resource["status"] == self.WEBHOOK_RESOURCE_STATUS_COMPLETED
        )

        return AzureDevOpsPullRequestData(
            action=action,
            repo_external_id=repository["id"],
            base_url=request_data["resourceContainers"]["account"]["baseUrl"],
            project_id=repository["project"]["id"],
            repo_owner=repository["project"]["name"],
            repo_name=repository["name"],
            repo_full_name=f"{repository['project']['name']}/{repository['name']}",
            head_sha=resource["lastMergeSourceCommit"]["commitId"],
            base_sha=resource["lastMergeTargetCommit"]["commitId"],
            pr_number=resource["pullRequestId"],
            updated_at=request_data["createdDate"],
            merged_at=(resource.get("closedDate") if is_merged else None),
            merge_commit_sha=resource.get("lastMergeCommit", {}).get("commitId"),
        )

    def parse_pull_request_action(self, request_data: dict) -> str:
        resource = request_data["resource"]

        action = request_data["eventType"]
        if action != self.WEBHOOK_ACTION_SYNCHRONIZE:
            return action

        status = resource["status"]
        if status in [
            self.WEBHOOK_RESOURCE_STATUS_ABANDONED,
            self.WEBHOOK_RESOURCE_STATUS_COMPLETED,
        ]:
            return self.WEBHOOK_ACTION_CLOSED

        message = request_data["message"]["text"]
        if self.WEBHOOK_MESSAGE_UPDATED in message:
            return action

        if self.WEBHOOK_MESSAGE_REOPENED in message:
            return self.WEBHOOK_ACTION_REOPENED

        return self.WEBHOOK_ACTION_IGNORE

    def format_pull_request_data_to_webhook_request_data(
        self,
        repository_data: GitRepositoryData,
        pull_request_data,
    ) -> Tuple[dict, bool]:
        data = {
            "createdDate": pull_request_data.creation_date,
            "eventType": self.WEBHOOK_ACTION_OPENED,
            "message": {"text": ""},
            "resource": {
                "closedDate": (str(pull_request_data.closed_date) if pull_request_data.closed_date else None),
                "lastMergeCommit": {
                    "commitId": (
                        pull_request_data.last_merge_commit.commit_id if pull_request_data.last_merge_commit else None
                    )
                },
                "lastMergeSourceCommit": {"commitId": pull_request_data.last_merge_source_commit.commit_id},
                "lastMergeTargetCommit": {"commitId": pull_request_data.last_merge_target_commit.commit_id},
                "pullRequestId": pull_request_data.pull_request_id,
                "repository": repository_data.raw_data,
            },
            "resourceContainers": {"account": {"baseUrl": repository_data.store_data["base_url"]}},
        }

        is_open = pull_request_data.status == "active"

        return data, is_open

    @retry_on_exceptions()
    def create_check_run(
        self,
        data: AzureDevOpsPullRequestData,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        old_external_data: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        if old_external_data and all(key in old_external_data for key in ["threadId", "commentId"]):
            self.api.delete_comment(
                data.repo_external_id,
                data.pr_number,
                old_external_data.get("threadId"),
                old_external_data.get("commentId"),
            )

        output = output or {"title": "Check run started"}
        response = self.api.post_comment(
            repository_id=data.repo_external_id,
            pull_request_id=data.pr_number,
            comment_content=self.output_to_comment(output),
            status=(
                CommentThreadStatus.FIXED if status == self.CHECK_RUN_STATUS_COMPLETED else CommentThreadStatus.ACTIVE
            ),
        )
        logger.info(f"Creating check run for PR {data.repo_full_name} with status {status} and conclusion {conclusion}")

        external_data = {"threadId": response.id, "commentId": response.comments[0].id}

        # TODO replace response.id with the real status check id when we implement status check
        return response.id, external_data

    @retry_on_exceptions()
    def update_check_run(
        self,
        data: AzureDevOpsPullRequestData,
        check_run_id,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        old_external_data: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        if old_external_data and all(key in old_external_data for key in ["threadId", "commentId"]):
            self.api.delete_comment(
                data.repo_external_id,
                data.pr_number,
                old_external_data.get("threadId"),
                old_external_data.get("commentId"),
            )

        logger.info(f"Updating check run for PR {data.repo_full_name} with status {status}")
        # TODO update the check run when we implement status check
        # Always create a new comment in Azure devops
        response = self.api.post_comment(
            data.repo_external_id,
            data.pr_number,
            self.output_to_comment(output),
            status=(
                CommentThreadStatus.FIXED if status == self.CHECK_RUN_STATUS_COMPLETED else CommentThreadStatus.ACTIVE
            ),
        )

        external_data = {"threadId": response.id, "commentId": response.comments[0].id}

        # TODO replace response.id with the real status check id when we implement status check
        return response.id, external_data

    @retry_on_exceptions()
    def complete_check_run(
        self,
        data: AzureDevOpsPullRequestData,
        check_run_id,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        old_external_data: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        if old_external_data and all(key in old_external_data for key in ["threadId", "commentId"]):
            self.api.delete_comment(
                data.repo_external_id,
                data.pr_number,
                old_external_data.get("threadId"),
                old_external_data.get("commentId"),
            )

        logger.info(f"Completing check run for PR {data.repo_full_name} with conclusion {conclusion}")
        # TODO update the check run when we implement status check
        # Always create a new comment in Azure devops
        response = self.api.post_comment(
            data.repo_external_id,
            data.pr_number,
            self.output_to_comment(output),
            status=CommentThreadStatus.FIXED,
        )

        external_data = {"threadId": response.id, "commentId": response.comments[0].id}

        # TODO replace response.id with the real status check id when we implement status check
        return response.id, external_data

    def output_to_comment(self, output):
        comment_text = []
        if "title" in output:
            comment_text.append(f"**{output['title']}**")

        if "summary" in output:
            comment_text.append(output["summary"])

        if "text" in output:
            comment_text.append(output["text"])

        return "\n\n".join(comment_text)

    def get_pull_request_commits(self, data: AzureDevOpsPullRequestData):
        shas = {data.head_sha}

        commits = self.api.get_pull_request_commits(data.repo_external_id, data.pr_number)

        shas.update(commit.commit_id for commit in commits)
        shas.discard(data.base_sha)

        return list(shas)

    def get_pull_request_files(self, data: AzureDevOpsPullRequestData):
        files = self.api.get_diff_files(data.repo_external_id, data.base_sha, data.head_sha)

        # parse files so they are in the format AI Engine expects
        return [
            {
                "filename": file["item"]["path"].lstrip("/"),
                # changeType can be a list like {"changeType": "delete, sourceRename"}
                "status": ", ".join(
                    self.FILE_STATUS_MAP.get(change_type.strip(), change_type.strip())
                    for change_type in file["changeType"].split(",")
                ),
            }
            for file in files
        ]

    def is_empty_repository(self, repository: GitRepositoryData):
        return not repository.raw_data.get("size")

    def get_repository_last_commit(self, repository: GitRepositoryData) -> Optional[GitCommitData]:
        last_commit = self.api.get_last_commit(repository.id, repository.owner)
        if last_commit:
            return GitCommitData(
                sha=last_commit.commit_id,
                date=last_commit.author.date,  # another possibility is committer.date
                raw_data=last_commit.as_dict(),
            )
        return None

    def get_repository_commit_by_date(self, repository: GitRepositoryData, date: datetime) -> Optional[GitCommitData]:
        # commits are sorted by date in descending order
        to_date = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        to_date = Serializer().query("to_date", to_date, "iso-8601")

        commit = self.api.get_last_commit(repository.id, repository.owner, to_date=to_date)
        if commit:
            return GitCommitData(
                sha=commit.commit_id,
                date=commit.author.date,
                raw_data=commit.as_dict(),
            )
        return None

    def get_repository_git_url(self, repository: GitRepositoryData) -> str:
        return self.api.get_repo_url(repository.owner, repository.name)

    def is_repository_connected(self, repository: Repository) -> bool:
        base_url = repository.external_data["base_url"]

        token = self.get_personal_access_token(base_url)

        if not token:
            return False

        repository_ids = self.get_base_url_repository_ids(base_url, token)
        return repository.external_id in repository_ids

    def get_base_url_repository_ids(self, base_url: str, token: str):
        self.load_base_url_repository_ids(base_url, token)
        return self._repo_ids_by_base_url[base_url]

    def load_base_url_repository_ids(self, base_url: str, token: str):
        if base_url not in self._repo_ids_by_base_url:
            try:
                self.init_api(
                    AzureDevOpsApiConfig(
                        base_url=base_url,
                        auth_token=token,
                    )
                )

                repositories = self.api.list_repos()
                self._repo_ids_by_base_url[base_url] = [str(repo.id) for repo in repositories]

            except Exception as e:
                self._repo_ids_by_base_url[base_url] = []

    def get_repository_pull_requests(
        self,
        repository: GitRepositoryData,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        state: Optional[str] = None,
    ) -> list[dict]:
        return self.api.get_repository_pull_requests(repository.id, min_date=since, max_date=until, status=state)

    @staticmethod
    def get_personal_access_token(base_url: str):
        data = DataProviderConnection.objects.filter(
            provider=AzureDevOpsIntegration().provider,
            data__base_url=base_url,
        ).values_list("data", flat=True)

        for datum in data:
            token = datum.get("personal_access_token")
            if token:
                return token

        return None

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return connection.data and connection.data.get("personal_access_token")

    @staticmethod
    def get_connected_repositories_with_integration(connection: DataProviderConnection):
        integration = AzureDevOpsIntegration()
        base_url = connection.data.get("base_url")
        auth_token = connection.data.get("personal_access_token")
        if not base_url or not auth_token:
            return []

        try:
            integration.init_api(AzureDevOpsApiConfig(base_url=base_url, auth_token=auth_token))
        except Exception as error:
            expired_str = "The Personal Access Token used has expired"
            invalid_str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            is_expired = expired_str in str(error)
            is_invalid = invalid_str in str(error)

            if is_expired:
                AzureDevOpsIntegration.update_expired_access_token(connection)
                logger.warning("Personal Access Token expired")
            elif is_invalid:
                AzureDevOpsIntegration.remove_invalid_access_token(connection)
                logger.warning("Personal Access Token is invalid")
            elif isinstance(error, AzureDevOpsAuthenticationError):
                AzureDevOpsIntegration.update_expired_access_token(connection)
                logger.warning("Azure DevOps authentication failed")
            else:
                logger.exception(
                    "Failed to connect to Azure DevOps",
                    extra={"base_url": base_url, "organization": connection.organization.name},
                )

            return []

        repositories = integration.api.list_repos()

        logger.info(f"Found {len(repositories)} repositories")

        return [
            (
                GitRepositoryData(
                    id=str(repo.id),
                    name=repo.name,
                    owner=repo.project.name,
                    raw_data=repo.as_dict(),
                    store_data={"base_url": integration.api.base_url},
                ),
                integration,
            )
            for repo in repositories
        ]

    def get_formatted_pull_request_with_repository_data(self, pull_request):
        repo_data = self.api.get_repository(pull_request.repository.external_id)
        formatted_repo_data = GitRepositoryData(
            id=str(repo_data.id),
            name=repo_data.name,
            owner=repo_data.project.name,
            raw_data=repo_data.as_dict(),
            store_data=pull_request.repository.external_data,
        )
        pr_data = self.api.get_pull_request(pull_request.pr_number)
        return formatted_repo_data, pr_data

    @staticmethod
    def disconnect(connection: DataProviderConnection):
        AzureDevOpsIntegration.update_expired_access_token(connection)

    @staticmethod
    def update_expired_access_token(connection: DataProviderConnection):
        if not connection.data:
            logger.info("No connection data")
            return

        token = connection.data.get("personal_access_token", None)
        if not token:
            logger.info("No personal access token")
            return

        # Expired Personal Access Tokens can be re-enabled on Azure DevOps, let's keep them just in case
        connection.data["expired_personal_access_token"] = token
        connection.data["personal_access_token"] = None

        connection.save()

    @staticmethod
    def remove_invalid_access_token(connection: DataProviderConnection):
        connection.data["personal_access_token"] = None
        connection.save()

    @staticmethod
    def get_repository_url(repository: Repository) -> str:
        return f"{repository.external_data['base_url']}{repository.owner}/_git/{repository.name}"

    @staticmethod
    def get_commit_url(repository: Repository, short_commit_hash: str) -> Optional[str]:
        repository_url = AzureDevOpsIntegration.get_repository_url(repository)
        full_commit_hash = AzureDevOpsIntegration.get_full_commit_hash(repository, short_commit_hash)
        if full_commit_hash:
            return f"{repository_url}/commit/{full_commit_hash}"
        return None

    @staticmethod
    def get_file_url(
        repository: Repository,
        file_name: str,
        commit_hash: str = None,
        branch_name: str = None,
    ) -> Optional[str]:
        if commit_hash:
            repository_url = AzureDevOpsIntegration.get_commit_url(repository, commit_hash)
            if repository_url and branch_name:
                repository_url += f"?refName=refs/heads/{branch_name}"
        else:
            repository_url = AzureDevOpsIntegration.get_repository_url(repository)

        if not repository_url:
            return None

        path_separator = "&" if "?" in repository_url else "?"
        encoded_filename = quote_plus(file_name)
        return f"{repository_url}{path_separator}path=/{encoded_filename}"

    @staticmethod
    def get_pull_request_url(pull_request: RepositoryPullRequest) -> str:
        repository_url = AzureDevOpsIntegration.get_repository_url(pull_request.repository)

        return f"{repository_url}/pullrequest/{pull_request.pr_number}"

    @staticmethod
    def get_missing_pull_requests(
        repository_data: List[GitRepositoryData],
        organization: Organization,
    ):
        """
        This is used to find missing pull requests.

        As PR ID is incremental per project only
        we need to check for missing PR's per project.

        This assumes all repositories are connected to
        the same Azure DevOps project.
        """
        projects = set(repo.owner for repo in repository_data)
        if len(projects) != 1:
            logger.warning("Cannot check for missing PRs from different projects")
            return []

        project = projects.pop()

        pr_numbers = RepositoryPullRequest.objects.filter(
            repository__external_id__in=[repo.id for repo in repository_data],
        ).values_list("pr_number", flat=True)

        missing_pr_numbers = find_missing_pr_ids(pr_numbers)
        for missing_pr_number in missing_pr_numbers:
            with push_scope() as scope:
                # Unable to provide repository or PR details here as it's
                # unknown which repository is missing the PR. Investigation
                # would have to start at the project level.
                scope.set_extra("organization", organization.name)
                scope.set_extra("project", project)
                scope.set_extra("pull request number", missing_pr_number)
                capture_message("Missing Azure pull request")

        return missing_pr_numbers

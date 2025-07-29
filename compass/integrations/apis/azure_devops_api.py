import logging
from dataclasses import dataclass
from urllib.parse import quote

from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v7_1.git.models import (
    Comment,
    CommentThread,
    GitBaseVersionDescriptor,
    GitCommitDiffs,
    GitPullRequestSearchCriteria,
    GitQueryCommitsCriteria,
    GitTargetVersionDescriptor,
)
from msrest.authentication import BasicAuthentication

from .base_rest_api import BaseRestApi

logger = logging.getLogger(__name__)


class CommentThreadStatus:
    UNKNOWN = 0
    ACTIVE = 1
    FIXED = 2
    WONT_FIX = 3
    CLOSED = 4
    BY_DESIGN = 5
    PENDING = 6


@dataclass(frozen=True)
class AzureDevOpsApiConfig:
    base_url: str
    auth_token: str


class AzureDevOpsApi(BaseRestApi):
    def __init__(self, config: AzureDevOpsApiConfig):
        self.base_url = config.base_url
        self.auth_token = config.auth_token
        self.git_client = self.get_git_client()

    def get_connection(self):
        return Connection(
            base_url=self.base_url,
            creds=BasicAuthentication("", self.auth_token),
        )

    def get_git_client(self):
        connection = self.get_connection()
        return connection.clients_v7_1.get_git_client()

    def get_repo_url(self, repo_owner, repo_name):
        repo_owner = quote(repo_owner)
        repo_name = quote(repo_name)

        # TODO: we should use a regex here probably, the base url could be in different formats
        # TODO base_url seems to include a backslash at the end, but gotta make sure that's the case
        url = f"{self.base_url}/{repo_owner}/_git/{repo_name}"
        logger.info(url)
        url = url.replace("https://", f"https://{self.auth_token}@")
        return url

    def post_comment(
        self,
        repository_id,
        pull_request_id,
        comment_content,
        status=CommentThreadStatus.ACTIVE,
    ):
        comment = Comment(content=comment_content, comment_type=1)
        comment_thread = CommentThread(comments=[comment], status=status)

        return self.git_client.create_thread(comment_thread, repository_id, pull_request_id)

    def update_comment(self, repo_external_id, pr_number, comment_thread_id, comment_content):
        comment = Comment(content=comment_content.replace("\\n", "\n"), comment_type=1)
        comment_thread = CommentThread(comments=[comment], status=CommentThreadStatus.FIXED)
        return self.git_client.update_thread(
            comment_thread,
            repo_external_id,
            pr_number,
            comment_thread_id,
        )

    def delete_comment(self, repo_external_id, pr_number, thread_id, comment_id):
        try:
            return self.git_client.delete_comment(
                repository_id=repo_external_id,
                pull_request_id=pr_number,
                thread_id=thread_id,
                comment_id=comment_id,
            )
        except Exception:
            logger.exception("Error deleting comment")
            return None

    def list_repos(self, include_disabled=False, include_hidden=False):
        repos = self.git_client.get_repositories(include_hidden=include_hidden)
        if not include_disabled:
            return [r for r in repos if not r.is_disabled]
        return repos

    def get_repository(self, repository_external_id):
        return self.git_client.get_repository(repository_external_id)

    def get_pull_request(self, pull_request_id):
        return self.git_client.get_pull_request_by_id(pull_request_id)

    def get_repository_pull_requests(self, repository_id, min_date=None, max_date=None, status=None):
        # TODO: min_date and max_date are in the documentation, but not implemented in the Python package
        # so we can't use date filtering for now
        # open a PR and get it merged
        # https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-requests/get-pull-requests?view=azure-devops-rest-7.1
        # https://github.com/microsoft/azure-devops-python-api/blob/30515b0d09d99a9cb7d23dc520f77ab644a9bdca/azure-devops/azure/devops/v7_1/git/models.py#L1898
        # search_criteria = GitPullRequestSearchCriteria(min_date=min_date, max_date=max_date)

        search_criteria = GitPullRequestSearchCriteria(status=status)
        return self.git_client.get_pull_requests(repository_id, search_criteria)

    def get_pull_request_commits(self, repository_id, pull_request_id):
        return self.git_client.get_pull_request_commits(repository_id, pull_request_id)

    def get_diff_files(self, repository_id, base_commit_id, target_commit_id):
        git_diff: GitCommitDiffs = self.git_client.get_commit_diffs(
            repository_id,
            base_version_descriptor=GitBaseVersionDescriptor(base_version=base_commit_id, base_version_type="commit"),
            target_version_descriptor=GitTargetVersionDescriptor(
                target_version=target_commit_id, target_version_type="commit"
            ),
        )

        return [item for item in git_diff.changes if not item["item"].get("isFolder", False)]

    def get_last_commit(self, repository_id, project, to_date=None):
        try:
            commits = self.git_client.get_commits(
                repository_id=repository_id,
                project=project,
                search_criteria=GitQueryCommitsCriteria(top=1, to_date=to_date),
            )
        except AzureDevOpsServiceError:
            logger.exception("Error getting last commit")
            commits = []

        return commits[0] if commits else None

    def list_commits(self, repository_id, project, from_date=None, to_date=None):
        try:
            commits = self.git_client.get_commits(
                repository_id=repository_id,
                project=project,
                search_criteria=GitQueryCommitsCriteria(from_date=from_date, to_date=to_date),
            )
        except AzureDevOpsServiceError:
            logger.exception("Error listing commits")
            commits = []

        return commits

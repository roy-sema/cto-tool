import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple

from mvp.models import DataProviderConnection, Organization, Repository, RepositoryPullRequest

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)


class GitServerBusyException(Exception):
    pass


class GitServerDisconnectException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class GitRepositoryData(ABC):
    id: str  # external id as per the git provider
    name: str  # name of the repository
    owner: str  # in GitHub this is the organization name, in Azure DevOps this is the project name, in BitBucket this is workspace.
    raw_data: dict = None  # raw data as received from the git provider
    store_data: dict = None  # data to be stored in the database as is


@dataclass(frozen=True, kw_only=True)
class GitCommitData(ABC):
    sha: str  # sha of the commit
    date: datetime  # date of the commit
    raw_data: dict = None  # raw data as received from the git provider


# TODO: we need a description of these fields here, so we don't have to read GitHub's API documentation when implementing a new provider
@dataclass(frozen=True, kw_only=True)
class PullRequestData(ABC):
    repo_external_id: str
    action: str
    repo_owner: str
    repo_name: str
    repo_full_name: str
    head_sha: str
    base_sha: str
    pr_number: int | str
    updated_at: datetime
    merged_at: datetime = None
    merge_commit_sha: str = None


class CheckRunStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class GitBaseIntegration(BaseIntegration, ABC):
    # These are GitHub constants, override in other providers if they are not the same
    CHECK_RUN_STATUS_IN_PROGRESS = "in_progress"
    CHECK_RUN_STATUS_COMPLETED = "completed"

    CHECK_RUN_CONCLUSION_SUCCESS = "success"
    CHECK_RUN_CONCLUSION_FAILURE = "failure"
    CHECK_RUN_CONCLUSION_NEUTRAL = "neutral"
    CHECK_RUN_CONCLUSION_CANCELLED = "cancelled"

    WEBHOOK_ACTION_CLOSED = "closed"
    WEBHOOK_ACTION_OPENED = "opened"
    WEBHOOK_ACTION_REOPENED = "reopened"
    WEBHOOK_ACTION_SYNCHRONIZE = "synchronize"

    WEBHOOK_CLOSED_ACTIONS = [WEBHOOK_ACTION_CLOSED]

    WEBHOOK_REQUEST_HEADER_ID = None

    def __init__(self):
        super().__init__()
        self.api = None

    @abstractmethod
    def init_api(self, config):
        pass

    @abstractmethod
    def parse_pull_request_data(self, request_data: dict):
        pass

    @abstractmethod
    def format_pull_request_data_to_webhook_request_data(
        self, repository_data: GitRepositoryData, pull_request_data
    ) -> Tuple[dict, bool]:
        pass

    @abstractmethod
    def create_check_run(
        self,
        data: PullRequestData,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        pass

    @abstractmethod
    def update_check_run(
        self,
        data: PullRequestData,
        check_run_id: str | int,
        status: str = None,
        conclusion: str = None,
        details_url: str = "",
        output: dict = None,
        **kwargs,
    ) -> Tuple[int, dict]:
        pass

    @abstractmethod
    def complete_check_run(
        self,
        data: PullRequestData,
        check_run_id: str | int,
        conclusion: str,
        output: dict,
        details_url: str,
        **kwargs,
    ) -> Tuple[int, dict]:
        pass

    @abstractmethod
    def get_pull_request_commits(self, data: PullRequestData):
        pass

    @abstractmethod
    def get_pull_request_files(self, data: PullRequestData):
        pass

    @abstractmethod
    def is_empty_repository(self, repository: GitRepositoryData):
        pass

    @abstractmethod
    def get_repository_last_commit(self, repository: GitRepositoryData) -> Optional[GitCommitData]:
        pass

    @abstractmethod
    def get_repository_commit_by_date(self, repository: GitRepositoryData, date: datetime) -> Optional[GitCommitData]:
        pass

    @abstractmethod
    def get_repository_git_url(self, repository: GitRepositoryData) -> str:
        pass

    @abstractmethod
    def is_repository_connected(self, repository: Repository) -> bool:
        pass

    @abstractmethod
    def get_repository_pull_requests(
        self,
        repository: GitRepositoryData,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        state: Optional[str] = None,
    ) -> list[dict]:
        pass

    @staticmethod
    @abstractmethod
    def get_connected_repositories_with_integration(connection: DataProviderConnection):
        pass

    @staticmethod
    @abstractmethod
    def disconnect(connection: DataProviderConnection):
        pass

    @staticmethod
    @abstractmethod
    def get_repository_url(repository: Repository) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_pull_request_url(pull_request: RepositoryPullRequest) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_commit_url(repository: Repository, commit_hash: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_file_url(repository: Repository, file_name: str, commit_hash: str = None, branch_name: str = None) -> str:
        pass

    @staticmethod
    def get_missing_pull_requests(repository_data: List[GitRepositoryData], organization: Organization):
        # TODO: implement if needed.
        return []

    @staticmethod
    def _get_branch_from_local_repo(repository: Repository) -> str | None:
        try:
            repo_dir = repository.get_download_directory()

            # Run git name-rev command to get the default branch
            result = subprocess.run(
                ["git", "name-rev", "--name-only", "HEAD"],
                cwd=repo_dir + "/" + repository.last_commit_sha,
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse the branch name
            # e.g., "remotes/origin/main" -> "main"
            # or "remotes/some-remote-name/main/feature/xyz" -> "main/feature/xyz"
            branch = result.stdout.strip()

            if not branch:
                return None

            parts = branch.split("/")
            if len(parts) > 2:
                return "/".join(parts[2:])
            else:
                return parts[-1] if parts else None

        except Exception:
            logger.exception(
                "Failed to get default branch from local git repository",
                extra={
                    "organization": repository.organization.name,
                    "repository": repository.name,
                    "provider": repository.provider.name,
                },
            )
            return None

    @staticmethod
    def get_full_commit_hash(repository: Repository, short_commit_hash: str) -> str | None:
        try:
            repo_dir = repository.get_download_directory()
            commit_repo_path = os.path.join(repo_dir, repository.last_commit_sha)
            git_dir = os.path.join(commit_repo_path, ".git")

            result = subprocess.run(
                [
                    "git",
                    f"--git-dir={git_dir}",
                    f"--work-tree={commit_repo_path}",
                    "rev-parse",
                    short_commit_hash,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            full_hash = result.stdout.strip()
            return full_hash if full_hash else None

        except (subprocess.SubprocessError, FileNotFoundError):
            logger.exception(
                "Failed to get full commit hash via git rev-parse",
                extra={
                    "organization": repository.organization.name,
                    "repository": repository.name,
                    "provider": repository.provider.name,
                },
            )
            return None

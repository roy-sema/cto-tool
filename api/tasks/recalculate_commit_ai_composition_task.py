import logging
from datetime import datetime
from typing import List

from django.utils import timezone

from api.tasks import ProcessPullRequestTask
from compass.integrations.apis import (
    AzureDevOpsApiConfig,
    BitBucketApiConfig,
    GitHubApiConfig,
)
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
    IntegrationFactory,
    PullRequestData,
)
from mvp.models import (
    Repository,
    RepositoryCommit,
    RepositoryFile,
    RepositoryPullRequest,
)
from mvp.tasks import ImportAIEngineDataTask
from mvp.utils import start_new_thread

logger = logging.getLogger(__name__)


# TODO: this is too expensive. We should have a DB model that
# allows quick aggregation of data without needing to re-calculate
class RecalculateCommitAICompositionTask:
    def __init__(self):
        self.importer = ImportAIEngineDataTask()
        self.force = False

    def run(self, commits: List[RepositoryCommit], force=False):
        self.force = force

        commits_sha = [commit.sha for commit in commits]
        pull_requests = RepositoryPullRequest.objects.filter(head_commit_sha__in=commits_sha).all()

        prs_by_sha = {}
        for pr in pull_requests:
            prs_by_sha.setdefault(pr.head_commit_sha, []).append(pr)

        repositories = set()
        for commit in commits:
            repository = commit.repository
            logger.info(f"Updating composition of commit {commit.sha} for repository {repository.full_name()}")
            self.update_commit(commit, prs_by_sha.get(commit.sha, []))

            if repository.last_commit_sha == commit.sha:
                repositories.add(repository)

        organizations = set()
        for repository in repositories:
            commit_index = commits_sha.index(repository.last_commit_sha)
            logger.info(f"Updating composition of repository {repository.full_name()}")
            self.update_repository(repository, commits[commit_index])
            organizations.add(repository.organization)

        for organization in organizations:
            self.update_organization_background(organization)

    def update_commit(self, commit: RepositoryCommit, pull_requests: List[RepositoryPullRequest]):
        self.update_commit_ai_fields(commit)

        for pr in pull_requests:
            logger.info(f"Updating composition of PR #{pr.pr_number} for repository {commit.repository.full_name()}")
            self.update_pull_request_ai_fields(commit, pr)

        self.update_pull_requests_status_checks_background(commit, pull_requests)

        self.importer.set_ai_percentages(commit)
        commit.last_recalculated_at = timezone.make_aware(datetime.utcnow())

        commit.save()

    def update_commit_ai_fields(self, commit: RepositoryCommit):
        commit.reset_ai_fields()

        files = commit.repositoryfile_set.prefetch_related(
            "repositoryfilechunk_set", "repositoryfilechunk_set__attestation"
        ).all()
        for file in files:
            if self.force or file.needs_composition_recalculation:
                self.update_file_ai_fields(file)

            self.importer.increment_commit_code_lines(commit, file)

    def update_file_ai_fields(self, file: RepositoryFile):
        file.reset_ai_fields()

        for chunk in file.repositoryfilechunk_set.all():
            label = chunk.get_label()
            # TODO: is this the cause of the % missmatch?
            ai_num_lines = chunk.code_num_lines if chunk.is_labeled_human else chunk.code_ai_num_lines
            self.importer.increment_file_chunk_lines(file, label, chunk.code_num_lines, ai_num_lines)

        file.last_recalculated_at = timezone.make_aware(datetime.utcnow())
        file.save()

    def update_pull_request_ai_fields(self, commit: RepositoryCommit, pull_request: RepositoryPullRequest):
        pull_request.reset_ai_fields()
        pull_request.code_num_lines = commit.code_num_lines
        pull_request.code_ai_num_lines = commit.code_ai_num_lines
        pull_request.code_ai_blended_num_lines = commit.code_ai_blended_num_lines
        pull_request.code_ai_pure_num_lines = commit.code_ai_pure_num_lines

        self.importer.set_ai_percentages(pull_request)
        pull_request.last_recalculated_at = timezone.make_aware(datetime.utcnow())
        pull_request.save()

    def update_repository(self, repository, commit):
        self.importer.copy_commit_stats_to_repository(commit, repository)
        repository.save()

    @start_new_thread
    def update_organization_background(self, organization):
        # TODO: we should throttle this, especially GBOM pre-computation
        self.importer.update_organization(organization)

    @start_new_thread
    def update_pull_requests_status_checks_background(
        self, commit: RepositoryCommit, pull_requests: List[RepositoryPullRequest]
    ):
        prs = [pr for pr in pull_requests if not pr.is_closed]
        if not prs:
            return

        base_commit = prs[0].base_commit()
        self.update_status_checks(
            repository=prs[0].repository,
            commit=commit,
            prs=prs,
            base_commit=base_commit,
        )

    def update_status_checks(
        self,
        repository: Repository,
        commit: RepositoryCommit,
        prs: List[RepositoryPullRequest],
        base_commit: RepositoryCommit = None,
    ):
        # TODO add tests
        integration = IntegrationFactory().get_integration(repository.provider.name)
        if type(integration) is GitHubIntegration:
            installation_id = repository.external_data.get("installation_id")
            config = GitHubApiConfig(installation_id=installation_id)
            integration.init_api(config)
        elif type(integration) is AzureDevOpsIntegration:
            base_url = repository.external_data.get("base_url")
            token = integration.get_personal_access_token(base_url)
            config = AzureDevOpsApiConfig(base_url=base_url, auth_token=token)
            integration.init_api(config)
        elif type(integration) is BitBucketIntegration:
            workspace = repository.external_data.get("workspace")
            connection = integration.get_workspace_connection(workspace)
            access_token, refresh_token = integration.get_connection_credentials(connection)

            config = BitBucketApiConfig(
                workspace=workspace,
                access_token=access_token,
                refresh_token=refresh_token,
            )
            integration.init_api(config, connection)
        else:
            # if it's not supported, don't continue
            return

        process_pr_task = ProcessPullRequestTask()
        process_pr_task.integration = integration

        packed_prs = [(pr, commit, repository) for pr in prs]
        # HACK: kinda
        process_pr_task.data = PullRequestData(
            action="attest",
            repo_external_id=repository.external_id,
            repo_owner=repository.owner,
            repo_name=repository.name,
            repo_full_name=repository.full_name(),
            head_sha=commit.sha,
            base_sha=base_commit.sha if base_commit else None,
            pr_number=prs[0].pr_number,
            updated_at=prs[0].updated_at,
        )

        old_external_data = process_pr_task.get_external_data_for_pull_requests(pull_requests=packed_prs)

        process_pr_task.check_rules_and_complete_check_run(
            pull_requests=packed_prs, old_external_data=old_external_data
        )

import json
import logging
import mimetypes
import os.path
import subprocess
import time
from math import ceil

import boto3
from botocore.config import Config
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from sentry_sdk import capture_exception, capture_message, push_scope

from compass.integrations.integrations import (
    CheckRunStatus,
    GitBaseIntegration,
    GitHubPullRequestData,
    GitRepositoryData,
    PullRequestData,
)
from mvp.models import (
    AITypeChoices,
    Repository,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
    RepositoryPullRequest,
    RepositoryPullRequestStatusCheck,
    RuleRiskChoices,
)
from mvp.services import PullRequestService, RuleService
from mvp.tasks import DownloadRepositoriesTask, ImportAIEngineDataTask
from mvp.utils import traceback_on_debug

logger = logging.getLogger(__name__)


class AnalysisTimeoutError(Exception):
    pass


boto3_config = Config(
    retries={
        "max_attempts": settings.BOTO3_CONFIG_RETRIES_MAX_ATTEMPTS,
        "mode": settings.BOTO3_CONFIG_RETRIES_MODE,
    },
    connect_timeout=settings.BOTO3_CONFIG_CONNECT_TIMEOUT,
    read_timeout=settings.BOTO3_CONFIG_READ_TIMEOUT,
)


class ProcessPullRequestTask:
    ERROR_ANALYSIS_FAILED = "Analysis failed"
    ERROR_ANALYSIS_TIMEOUT = "Analysis took too long"
    ERROR_DOWNLOAD_FAILED = "Download failed"
    ERROR_IMPORT_FAILED = "Import failed"
    ERROR_NO_REPOSITORIES = "No repositories found"

    MESSAGE_CODE_OK = "The code in this PR meets GenAI guidance."
    MESSAGE_CODE_NOT_OK = "Action recommended. The code in this PR does not meet GenAI guidance."

    SUMMARY_ERROR = "Sema GenAI Detector could not complete, an error has occurred"
    SUMMARY_FAILURE = "The code in this PR does not meet one or more GenAI guidance rules."
    SUMMARY_SUCCESS = "The code in this PR meets all GenAI guidance rules."
    SUMMARY_STILL_RUNNING = "Sema GenAI Detector is still running."

    TITLE_ERROR = "An Error Occurred"
    TITLE_FAILURE = "Failure"
    TITLE_SUCCESS = "Sema GenAI Detector has completed successfully"
    TITLE_PASS = "The code meets GenAI guidance."
    TITLE_NOT_PASS = "Action recommended."
    TITLE_STILL_RUNNING = "Analysis is taking longer than expected"

    @property
    def queue_conditions(self):
        small_threshold = settings.QUEUE_NUM_LINES_THRESHOLD_SMALL
        medium_threshold = settings.QUEUE_NUM_LINES_THRESHOLD_MEDIUM
        return [
            (
                lambda num_files: num_files < small_threshold,
                settings.SQS_QUEUE_URL_SMALL,
            ),
            (
                lambda num_files: small_threshold <= num_files < medium_threshold,
                settings.SQS_QUEUE_URL_MEDIUM,
            ),
            (
                lambda num_files: num_files >= medium_threshold,
                settings.SQS_QUEUE_URL_LARGE,
            ),
        ]

    def __init__(self):
        self.data = None
        self.check_run_id = None
        self.integration = None

    def run(self, data: PullRequestData, integration: GitBaseIntegration):
        try:
            self.data = data
            self.integration = integration
            self.process()
            return True

        except Exception as error:
            with push_scope() as scope:
                scope.set_extra("request_data", self.data)
                traceback_on_debug()
                capture_exception(error)

            if self.check_run_id:
                details_url = self.get_details_url(self.data.repo_external_id, self.data.pr_number)
                conclusion, output = self.get_status_check_conclusion_and_output(
                    check_status=CheckRunStatus.ERROR, details_url=details_url
                )
                self.complete_check_run(
                    conclusion=conclusion,
                    output=output,
                    details_url=details_url,
                )

            return False

    def process(self):
        data = self.data

        repositories = self.get_repositories(self.integration.provider, data.repo_external_id, data)

        if not repositories.filter(organization__status_check_enabled=True).exists():
            logger.warning(self.ERROR_NO_REPOSITORIES)
            return

        logger.info(f"Processing pull request {data.pr_number} for {len(repositories)} repositories")

        if data.action in self.integration.WEBHOOK_CLOSED_ACTIONS:
            if data.merged_at:
                self.process_merge(repositories)

            self.close_pull_requests(repositories, data.pr_number)
            return

        if data.action == self.integration.WEBHOOK_ACTION_REOPENED:
            self.reopen_pull_requests(repositories, data.pr_number)
            return

        self.process_pull_request(repositories)

    def close_pull_requests(self, repositories, pr_number):
        pull_requests = RepositoryPullRequest.objects.filter(
            repository__in=repositories, pr_number=pr_number, is_closed=False
        )
        pull_requests.update(is_closed=True)

    def reopen_pull_requests(self, repositories, pr_number):
        pull_requests = RepositoryPullRequest.objects.filter(
            repository__in=repositories, pr_number=pr_number, is_closed=True
        )
        pull_requests.update(is_closed=False)

    def process_pull_request(self, repositories):
        data = self.data

        commits = self.create_commits(
            repositories,
            sha=data.head_sha,
            date_time=data.updated_at,
        )

        analysis_folder = commits[0][0].get_download_directory(is_pull_request=True)

        # This prevents multiple analysis for the same PR commit, due to repeated webhooks for example
        if os.path.exists(analysis_folder):
            logger.info(f"Analysis folder already exists: {analysis_folder}")
            return

        pull_requests = self.create_pull_requests(commits, data.base_sha, data.head_sha, data.pr_number)

        old_external_data = self.get_external_data_for_pull_requests(pull_requests)

        self.check_run_id, external_data = self.integration.create_check_run(data, old_external_data=old_external_data)

        self.create_repository_pull_request_status_check(
            pull_requests=pull_requests,
            status=GitBaseIntegration.CHECK_RUN_STATUS_IN_PROGRESS,
            external_data=external_data,
        )

        analysis_file = self.get_analysis_file(analysis_folder)

        for commit in commits:
            commit[0].analysis_file = analysis_file
            commit[0].save()

        files = self.download_pull_request_files(data=data, download_directory=analysis_folder)

        if files is None:
            self.mark_commits_failure([commit[0] for commit in commits])
            raise Exception(self.ERROR_DOWNLOAD_FAILED)

        try:
            analyzed = self.analyze_files(analysis_folder, files)
        except AnalysisTimeoutError:
            self.mark_commits_failure([commit[0] for commit in commits])
            raise Exception(self.ERROR_ANALYSIS_TIMEOUT)

        if not analyzed:
            self.mark_commits_failure([commit[0] for commit in commits])
            raise Exception(self.ERROR_ANALYSIS_FAILED)

        imported = self.import_data(pull_requests)
        if not imported:
            self.mark_commits_failure([commit[0] for commit in commits])
            raise Exception(self.ERROR_IMPORT_FAILED)

        self.check_rules_and_complete_check_run(pull_requests, external_data)

    def check_rules_and_complete_check_run(self, pull_requests, old_external_data=None):
        logger.info(f"Checking rules for {len(pull_requests)} pull requests")

        pull_request_pass = self.check_rules(pull_requests)
        if pull_request_pass:
            status = CheckRunStatus.SUCCESS
            title = self.TITLE_PASS
        else:
            status = CheckRunStatus.FAILURE
            title = self.TITLE_NOT_PASS

        single_pr = pull_requests[0][0] if pull_requests else None
        message = self.get_check_run_message(pull_request_pass)
        details_url = self.get_details_url(self.data.repo_external_id, self.data.pr_number)

        logger.info(f"Check run status: {status}")
        logger.info(f"Check run id: {self.check_run_id}")

        conclusion, output = self.get_status_check_conclusion_and_output(
            check_status=status,
            details_url=details_url,
            title=title,
            message=message,
            pull_request_pass=pull_request_pass,
            pull_request=single_pr,
        )

        # Mark as neutral instead of failed. Keep title and description as they are
        # TODO: handle multiple organizations with different setting
        if single_pr and not pull_request_pass and not single_pr.repository.organization.status_check_mark_as_failed:
            conclusion = self.integration.CHECK_RUN_CONCLUSION_NEUTRAL

        if self.check_run_id is not None:
            check_run_id, external_data = self.complete_check_run(
                conclusion=conclusion,
                output=output,
                details_url=details_url,
                old_external_data=old_external_data,
            )
        else:
            check_run_id, external_data = self.create_completed_check_run(
                conclusion=conclusion,
                details_url=details_url,
                output=output,
                old_external_data=old_external_data,
            )
            self.check_run_id = check_run_id

        self.create_repository_pull_request_status_check(
            pull_requests=pull_requests,
            status=conclusion,
            output=output,
            external_data=external_data,
        )

    def process_merge(self, repositories):
        # GitHub, Azure DevOps and BitBucket create a
        # new SHA whenever we merge (even with rebase/squash).
        # That means the next download cron will pull the most recent commit
        # Since we are no longer comparing against the base repo, there's no need
        # to download and analyze every time there's a merge.
        # So do nothing for now.
        pass

    def create_commits(self, repositories, sha, date_time):
        commits = []
        for repo in repositories:
            commit, _ = self.get_or_create_commit(repo, sha, date_time)
            commits.append((commit, repo))

        return commits

    def get_or_create_commit(self, repository, sha, date_time):
        return RepositoryCommit.objects.get_or_create(
            repository=repository,
            sha=sha,
            defaults={"date_time": date_time},
        )

    def create_pull_requests(self, commits, base_sha, head_sha, pr_number):
        pull_requests = []
        for commit, repo in commits:
            pull_request, created = RepositoryPullRequest.objects.get_or_create(
                repository=repo,
                pr_number=pr_number,
                defaults={"base_commit_sha": base_sha, "head_commit_sha": head_sha},
            )
            if not created and (pull_request.base_commit_sha != base_sha or pull_request.head_commit_sha != head_sha):
                pull_request.base_commit_sha = base_sha
                pull_request.head_commit_sha = head_sha
                pull_request.save()

            commit.pull_requests.add(pull_request)

            pull_requests.append((pull_request, commit, repo))

        return pull_requests

    def download_pull_request_files(
        self,
        data: PullRequestData,
        download_directory: str,
    ):
        os.umask(0o002)
        git_url = self.integration.get_repository_git_url(
            GitRepositoryData(
                id=data.repo_external_id,
                name=data.repo_name,
                owner=data.repo_owner,
            )
        )

        downloader = DownloadRepositoriesTask()
        os.makedirs(download_directory, exist_ok=True)
        cloned = downloader.clone_repository(git_url, data.head_sha, download_directory)
        if not cloned:
            return None

        commits = self.integration.get_pull_request_commits(data)
        changed_files = self.integration.get_pull_request_files(data)

        self.write_metadata(
            directory=download_directory,
            pr_number=data.pr_number,
            commits=commits,
            changed_files=changed_files,
        )

        return changed_files

    def import_data(self, pull_requests, max_attempts=3, delay=1):
        imported = False
        importer = ImportAIEngineDataTask()

        logger.info(f"Importing data for {len(pull_requests)} pull requests")
        for pull_request, commit, repo in pull_requests:
            logger.info(f"Importing data for {repo}, {commit}, {pull_request}")
            # if one is imported successfully, we return success
            if importer.process_commit(repo, commit, pull_request=pull_request):
                imported = True

        if not imported and max_attempts > 0:
            time.sleep(delay)
            return self.import_data(pull_requests, max_attempts - 1, delay * 2)

        logger.info(f"Imported: {imported}")
        return imported

    def write_metadata(self, directory, pr_number, commits, changed_files):
        metadata = {
            "pr_number": pr_number,
            "commits": commits,
            "changed_files": changed_files,
        }
        file_path = os.path.join(directory, "metadata.json")
        with open(file_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def analyze_files(self, repository_path, files):
        queue_url = self.get_analysis_queue_url(repository_path, files)
        if queue_url:
            return self.analyze_files_worker(repository_path, queue_url)

        return self.analyze_files_local(repository_path)

    def analyze_files_worker(self, repository_path, queue_url):
        sqs = boto3.client(
            "sqs",
            region_name=settings.SQS_REGION,
            config=boto3_config,
        )
        message = json.dumps({"repository_path": repository_path, "selective": True})
        response = sqs.send_message(QueueUrl=queue_url, MessageBody=message)
        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            with push_scope() as scope:
                scope.set_extra("sqs_response", response)
                logger.info("Failed to send message to SQS")
                # Fallback to local analysis in case SQS is down or not responsive
                return self.analyze_files_local(repository_path)

        return self.check_remote_analysis_status(repository_path)

    def check_remote_analysis_status(self, repository_path):
        interval = settings.REMOTE_ANALYSIS_CHECK_INTERVAL
        soft_max_time = settings.REMOTE_ANALYSIS_SOFT_MAX_TIME
        fail_max_time = settings.REMOTE_ANALYSIS_FAIL_MAX_TIME
        soft_max_attempts = ceil(soft_max_time / interval) - 1
        max_attempts = ceil(fail_max_time / interval) - 1
        for attempt in range(max_attempts):
            time.sleep(interval)

            if self.is_analysis_complete(repository_path):
                elapsed_time = attempt * interval
                logger.info(f"Analysis completed in ~{elapsed_time}s")
                return True

            if attempt == soft_max_attempts:
                logger.info("Analysis is taking longer than expected")
                self.integration.update_check_run(
                    self.data,
                    self.check_run_id,
                    output={
                        "title": self.TITLE_STILL_RUNNING,
                        "summary": self.SUMMARY_STILL_RUNNING,
                    },
                )

        raise AnalysisTimeoutError

    def analyze_files_local(self, repository_path):
        log_path = f"{repository_path}.analysis.log"
        with open(log_path, "w") as log_file:
            ai_engine_python = settings.AI_ENGINE_PYTHON
            subprocess.run(
                [ai_engine_python, "main.py", repository_path, "--selective"],
                cwd=settings.AI_ENGINE_DIRECTORY,
                stdout=log_file if not settings.DEBUG else None,
                stderr=subprocess.STDOUT,
            )

            if not settings.DEBUG:
                logger.info(f"Analysis log: {log_path}")

        return self.is_analysis_complete(repository_path)

    def is_analysis_complete(self, repository_path):
        return os.path.exists(self.get_analysis_file(repository_path))

    def get_analysis_queue_url(self, repository_path, files):
        if settings.DEBUG:
            return None

        num_lines = self.count_files_lines(repository_path, files)
        for condition, queue_url in self.queue_conditions:
            if condition(num_lines):
                return queue_url

        with push_scope() as scope:
            scope.set_extra("repository_path", repository_path)
            scope.set_extra("request_data", self.data)
            capture_message(
                f"Queue condition can't be resolved for {num_lines} lines",
                level="error",
            )

        return None

    def count_files_lines(self, repository_path, files):
        file_paths = [os.path.join(repository_path, file["filename"]) for file in files]

        # This is an approximation, as we don't support all text files
        num_lines = 0
        for file_path in file_paths:
            file_type, _ = mimetypes.guess_type(file_path)
            if file_type and "text" in file_type:
                result = subprocess.run(["wc", "-l", file_path], stdout=subprocess.PIPE, text=True)

                split_result = result.stdout.split()
                if split_result:
                    num_lines += int(split_result[0])

        return num_lines

    def get_status_check_conclusion_and_output(self, check_status, details_url, **kwargs):
        if check_status == CheckRunStatus.SUCCESS:
            conclusion, output = self.get_check_run_data_success(details_url, **kwargs)
        elif check_status == CheckRunStatus.FAILURE:
            conclusion, output = self.get_check_run_data_failure(details_url, **kwargs)
        elif check_status == CheckRunStatus.ERROR:
            conclusion, output = self.get_check_run_data_error()
        else:
            conclusion, output = self.get_check_run_data_unknown(check_status)

        return conclusion, output

    def create_completed_check_run(self, conclusion, output, details_url, old_external_data=None):
        logger.info(f"Creating completed check: {conclusion} {details_url}")
        return self.integration.create_check_run(
            self.data,
            status=self.integration.CHECK_RUN_STATUS_COMPLETED,
            conclusion=conclusion,
            details_url=details_url,
            output=output,
            old_external_data=old_external_data,
        )

    def complete_check_run(self, conclusion, output, details_url, old_external_data=None):
        return self.integration.complete_check_run(
            data=self.data,
            check_run_id=self.check_run_id,
            conclusion=conclusion,
            output=output,
            details_url=details_url,
            old_external_data=old_external_data,
        )

    def get_check_run_data_success(self, details_url, **kwargs):
        conclusion = self.integration.CHECK_RUN_CONCLUSION_SUCCESS
        title = kwargs.pop("title", self.TITLE_SUCCESS)
        summary = self.SUMMARY_SUCCESS
        return conclusion, self.get_check_run_detail_output(conclusion, title, summary, details_url, **kwargs)

    def get_check_run_data_failure(self, details_url, **kwargs):
        conclusion = self.integration.CHECK_RUN_CONCLUSION_FAILURE
        title = kwargs.pop("title", self.TITLE_FAILURE)
        summary = self.SUMMARY_FAILURE
        return conclusion, self.get_check_run_detail_output(conclusion, title, summary, details_url, **kwargs)

    def get_check_run_data_error(self):
        return self.integration.CHECK_RUN_CONCLUSION_CANCELLED, {
            "title": self.TITLE_ERROR,
            "summary": self.SUMMARY_ERROR,
        }

    def get_check_run_data_unknown(self, check_status):
        logger.error(f"Unknown check status: {check_status}")
        return self.integration.CHECK_RUN_CONCLUSION_NEUTRAL, {}

    def get_check_run_detail_output(
        self,
        conclusion,
        title,
        summary,
        details_url,
        message="",
        pull_request_pass=None,
        pull_request=None,
    ):
        return {
            "title": title,
            "summary": summary,
            "text": self.get_markdown_message(
                conclusion,
                message,
                details_url,
                pull_request_pass,
                pull_request,
            ),
        }

    def get_markdown_message(
        self,
        conclusion,
        message,
        details_url,
        pull_request_pass,
        pull_request,
    ):
        pr_data = PullRequestService().get_markdown_render_data(pull_request) if pull_request else {}

        return render_to_string(
            "markdown/status-check.md",
            {
                "conclusion": conclusion,
                "message": message,
                "details_url": details_url,
                "pull_request_pass": pull_request_pass,
                **pr_data,
            },
        )

    def check_rules(self, pull_requests):
        validations = []
        for pull_request, commit, repo in pull_requests:
            # if no files analyzed, don't evaluate rules
            if not pull_request.analysis_num_files:
                validations.append(True)
                continue

            rules = list(RuleService.get_organization_rules(repo.organization))
            if repo.group:
                rules += repo.group.rules.all()

            percentages = {
                AITypeChoices.PURE: pull_request.percentage_ai_pure(),
                AITypeChoices.BLENDED: pull_request.percentage_ai_blended(),
                AITypeChoices.OVERALL: pull_request.percentage_ai_overall(),
            }
            for rule in rules:
                if rule.risk == RuleRiskChoices.STRENGTH:
                    continue

                validations.append(not RuleService.validate_rule_conditions(rule, percentages))

        return all(validations)

    def get_check_run_message(self, pull_request_pass):
        return self.MESSAGE_CODE_OK if pull_request_pass else self.MESSAGE_CODE_NOT_OK

    def get_repositories(self, provider, external_id, data):
        logger.info(f"Getting repositories for {provider} {external_id}")
        qs = Repository.objects.filter(provider=provider, external_id=external_id)

        if isinstance(data, GitHubPullRequestData):
            qs = qs.filter(external_data__installation_id=str(data.installation_id))

        return qs.prefetch_related("organization", "group", "group__rules", "group__rules__conditions")

    def get_details_url(self, external_id, pr_number):
        pull_path = reverse(
            "pull_request_scan",
            kwargs={
                "external_id": external_id,
                "pr_number": pr_number,
            },
        )
        return f"{settings.SITE_DOMAIN}{pull_path}"

    def get_analysis_file(self, analysis_folder):
        return f"{analysis_folder}.csv"

    def mark_commits_failure(self, commits):
        for commit in commits:
            commit.status = RepositoryCommitStatusChoices.FAILURE
            commit.save()

    def create_repository_pull_request_status_check(self, pull_requests, status, output=None, external_data=None):
        try:
            for pr, commit, repo in pull_requests:
                RepositoryPullRequestStatusCheck.objects.create(
                    pull_request=pr,
                    status_check_id=self.check_run_id,
                    status=status,
                    message=output.get("text") if output else None,
                    external_data=external_data,
                )
        except Exception as error:
            with push_scope() as scope:
                data = self.data
                scope.set_extra("request_data", self.data)
                capture_exception(error)
                logger.exception(
                    f"error creating status check",
                    extra={
                        "repository_owner": data.repo_owner,
                        "repository_name": data.repo_name,
                        "pull_request_number": data.pr_number,
                    },
                )

    def get_external_data_for_pull_requests(self, pull_requests: list[tuple[RepositoryPullRequest, any, any]]) -> dict:
        external_data = (
            RepositoryPullRequestStatusCheck.objects.filter(
                pull_request__in=[pr[0] for pr in pull_requests],
                pull_request__is_closed=False,
            )
            .order_by("pull_request", "-created_at")
            .distinct("pull_request")
        )
        external_data = external_data[0].external_data if external_data else None
        return external_data

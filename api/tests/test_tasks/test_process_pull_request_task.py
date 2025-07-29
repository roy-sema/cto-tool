import logging
from unittest.mock import ANY, MagicMock, patch

from django.conf import settings
from django.test import TestCase
from parameterized import parameterized

from api.tasks import AnalysisTimeoutError, ProcessPullRequestTask
from api.tests.mixins import WebhooksDataTestMixin
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
)


class ProcessPullRequestTaskMixin(WebhooksDataTestMixin):
    # set those when using the mixin
    webhooks = None
    integration = None

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.process")
    def test_run_success(self, webhook, mock_process):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        processor = ProcessPullRequestTask()
        data = self.integration().parse_pull_request_data(webhook_data)
        integration = MagicMock()

        result = processor.run(data, integration)

        mock_process.assert_called_once()
        self.assertTrue(result)

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.process")
    def test_run_exception(self, webhook, mock_process):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        processor = ProcessPullRequestTask()
        data = self.integration().parse_pull_request_data(webhook_data)
        integration = MagicMock()
        mock_process.side_effect = Exception("Test exception")

        result = processor.run(data, integration)

        mock_process.assert_called_once()
        self.assertFalse(result)

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.process")
    @patch("api.tasks.ProcessPullRequestTask.complete_check_run")
    def test_run_exception_with_check_run_id(self, webhook, mock_complete_check_run, mock_process):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        processor = ProcessPullRequestTask()
        processor.check_run_id = 123
        data = self.integration().parse_pull_request_data(webhook_data)
        integration = MagicMock()
        mock_process.side_effect = Exception("Test exception")

        result = processor.run(data, integration)

        mock_process.assert_called_once()
        mock_complete_check_run.assert_called_once()
        self.assertFalse(result)

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.close_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.reopen_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.process_pull_request")
    def test_process_no_repositories_found(
        self,
        webhook,
        mock_process_pull_request,
        mock_reopen_pull_requests,
        mock_close_pull_requests,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = False
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = MagicMock()
        processor.process()

        mock_process_pull_request.assert_not_called()
        mock_close_pull_requests.assert_not_called()
        mock_reopen_pull_requests.assert_not_called()

    @parameterized.expand(
        [
            WebhooksDataTestMixin.WEBHOOK_OPENED,
            WebhooksDataTestMixin.WEBHOOK_SYNCHRONIZE,
        ]
    )
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.process_merge")
    @patch("api.tasks.ProcessPullRequestTask.close_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.reopen_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.process_pull_request")
    def test_process_pull_request(
        self,
        webhook,
        mock_process_pull_request,
        mock_reopen_pull_requests,
        mock_close_pull_requests,
        mock_process_merge,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = self.integration
        processor.process()

        mock_process_merge.assert_not_called()
        mock_close_pull_requests.assert_not_called()
        mock_reopen_pull_requests.assert_not_called()
        mock_process_pull_request.assert_called_once()

    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.process_merge")
    @patch("api.tasks.ProcessPullRequestTask.close_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.reopen_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.process_pull_request")
    def test_process_merged(
        self,
        mock_process_pull_request,
        mock_reopen_pull_requests,
        mock_close_pull_requests,
        mock_process_merge,
        mock_get_repositories,
    ):
        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(self.webhooks[WebhooksDataTestMixin.WEBHOOK_MERGED])
        processor.integration = self.integration
        processor.process()

        mock_process_merge.assert_called_once()
        mock_close_pull_requests.assert_called_once()
        mock_reopen_pull_requests.assert_not_called()
        mock_process_pull_request.assert_not_called()

    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.process_merge")
    @patch("api.tasks.ProcessPullRequestTask.close_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.reopen_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.process_pull_request")
    def test_process_not_merged(
        self,
        mock_process_pull_request,
        mock_reopen_pull_requests,
        mock_close_pull_requests,
        mock_process_merge,
        mock_get_repositories,
    ):
        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(
            self.webhooks[WebhooksDataTestMixin.WEBHOOK_NOT_MERGED]
        )
        processor.integration = self.integration
        processor.process()

        mock_process_merge.assert_not_called()
        mock_close_pull_requests.assert_called_once()
        mock_reopen_pull_requests.assert_not_called()
        mock_process_pull_request.assert_not_called()

    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.process_merge")
    @patch("api.tasks.ProcessPullRequestTask.close_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.reopen_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.process_pull_request")
    def test_process_reopened(
        self,
        mock_process_pull_request,
        mock_reopen_pull_requests,
        mock_close_pull_requests,
        mock_process_merge,
        mock_get_repositories,
    ):
        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(
            self.webhooks[WebhooksDataTestMixin.WEBHOOK_REOPENED]
        )
        processor.integration = self.integration
        processor.process()

        mock_process_merge.assert_not_called()
        mock_close_pull_requests.assert_not_called()
        mock_reopen_pull_requests.assert_called_once()
        mock_process_pull_request.assert_not_called()

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.create_commits")
    @patch("os.path.exists")
    @patch("api.tasks.ProcessPullRequestTask.get_analysis_file")
    @patch("api.tasks.ProcessPullRequestTask.create_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.download_pull_request_files")
    @patch("api.tasks.ProcessPullRequestTask.analyze_files")
    def test_process_pull_request_download_exists(
        self,
        webhook,
        mock_analyze_files,
        mock_download_pull_request_files,
        mock_create_pull_requests,
        mock_get_analysis_file,
        mock_os_path_exists,
        mock_create_commits,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        mock_analyze_files.return_value = False
        mock_get_analysis_file.return_value = MagicMock()
        mock_create_commits.return_value = MagicMock()
        mock_os_path_exists.return_value = True
        mock_create_pull_requests.return_value = MagicMock()
        mock_download_pull_request_files.return_value = []
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = MagicMock()

        processor.process()

        processor.integration.create_check_run.assert_not_called()

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.create_commits")
    @patch("os.path.exists")
    @patch("api.tasks.ProcessPullRequestTask.get_analysis_file")
    @patch("api.tasks.ProcessPullRequestTask.create_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.download_pull_request_files")
    @patch("api.tasks.ProcessPullRequestTask.analyze_files")
    def test_process_pull_request_download_failed(
        self,
        webhook,
        mock_analyze_files,
        mock_download_pull_request_files,
        mock_create_pull_requests,
        mock_get_analysis_file,
        mock_os_path_exists,
        mock_create_commits,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        mock_analyze_files.return_value = False
        mock_get_analysis_file.return_value = MagicMock()
        mock_create_commits.return_value = MagicMock()
        mock_os_path_exists.return_value = False
        mock_create_pull_requests.return_value = MagicMock()
        mock_download_pull_request_files.return_value = None
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = MagicMock()
        processor.integration.create_check_run.return_value = 1, {}

        with self.assertRaises(Exception) as context:
            processor.process()

        self.assertEqual(ProcessPullRequestTask.ERROR_DOWNLOAD_FAILED, str(context.exception))
        processor.integration.create_check_run.assert_called_once()

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.create_commits")
    @patch("os.path.exists")
    @patch("api.tasks.ProcessPullRequestTask.get_analysis_file")
    @patch("api.tasks.ProcessPullRequestTask.create_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.download_pull_request_files")
    @patch("api.tasks.ProcessPullRequestTask.analyze_files")
    def test_process_pull_request_analysis_failed(
        self,
        webhook,
        mock_analyze_files,
        mock_download_pull_request_files,
        mock_create_pull_requests,
        mock_get_analysis_file,
        mock_os_path_exists,
        mock_create_commits,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        mock_analyze_files.return_value = False
        mock_get_analysis_file.return_value = MagicMock()
        mock_create_commits.return_value = MagicMock()
        mock_os_path_exists.return_value = False
        mock_create_pull_requests.return_value = MagicMock()
        mock_download_pull_request_files.return_value = ["file1", "file2"]
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = MagicMock()
        processor.integration.create_check_run.return_value = 1, {}

        with self.assertRaises(Exception) as context:
            processor.process()

        self.assertEqual(ProcessPullRequestTask.ERROR_ANALYSIS_FAILED, str(context.exception))
        processor.integration.create_check_run.assert_called_once()

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.create_commits")
    @patch("os.path.exists")
    @patch("api.tasks.ProcessPullRequestTask.get_analysis_file")
    @patch("api.tasks.ProcessPullRequestTask.create_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.download_pull_request_files")
    @patch("api.tasks.ProcessPullRequestTask.analyze_files")
    @patch("api.tasks.ProcessPullRequestTask.import_data")
    def test_process_pull_request_import_failed(
        self,
        webhook,
        mock_import_data,
        mock_analyze_files,
        mock_download_pull_request_files,
        mock_create_pull_requests,
        mock_get_analysis_file,
        mock_os_path_exists,
        mock_create_commits,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        mock_import_data.return_value = False
        mock_get_analysis_file.return_value = MagicMock()
        mock_create_commits.return_value = MagicMock()
        mock_os_path_exists.return_value = False
        mock_create_pull_requests.return_value = MagicMock()
        mock_download_pull_request_files.return_value = ["file1", "file2"]
        mock_analyze_files.return_value = MagicMock()
        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = MagicMock()
        processor.integration.create_check_run.return_value = 1, {}

        with self.assertRaises(Exception) as context:
            processor.process()

        self.assertEqual(ProcessPullRequestTask.ERROR_IMPORT_FAILED, str(context.exception))
        processor.integration.create_check_run.assert_called_once()

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    @patch("api.tasks.ProcessPullRequestTask.get_repositories")
    @patch("api.tasks.ProcessPullRequestTask.create_commits")
    @patch("os.path.exists")
    @patch("api.tasks.ProcessPullRequestTask.get_analysis_file")
    @patch("api.tasks.ProcessPullRequestTask.create_pull_requests")
    @patch("api.tasks.ProcessPullRequestTask.download_pull_request_files")
    @patch("api.tasks.ProcessPullRequestTask.analyze_files")
    @patch("api.tasks.ProcessPullRequestTask.import_data")
    @patch("api.tasks.ProcessPullRequestTask.check_rules")
    @patch("api.tasks.ProcessPullRequestTask.complete_check_run")
    @patch("api.tasks.ProcessPullRequestTask.get_status_check_conclusion_and_output")
    def test_process_pull_request_success(
        self,
        webhook,
        mock_get_status_check_conclusion_and_output,
        mock_complete_check_run,
        mock_check_rules,
        mock_import_data,
        mock_analyze_files,
        mock_download_pull_request_files,
        mock_create_pull_requests,
        mock_get_analysis_file,
        mock_os_path_exists,
        mock_create_commits,
        mock_get_repositories,
    ):
        if not (webhook_data := self.webhooks.get(webhook)):
            return

        mock_get_repositories.return_value.filter.return_value.exists.return_value = True
        mock_get_analysis_file.return_value = MagicMock()
        mock_create_commits.return_value = MagicMock()
        mock_os_path_exists.return_value = False
        mock_create_pull_requests.return_value = MagicMock()
        mock_download_pull_request_files.return_value = ["file1", "file2"]
        mock_analyze_files.return_value = True
        mock_import_data.return_value = True
        mock_check_rules.return_value = True
        mock_get_status_check_conclusion_and_output.return_value = ("success", {})
        mock_complete_check_run.return_value = 1, {}

        processor = ProcessPullRequestTask()
        processor.data = self.integration().parse_pull_request_data(webhook_data)
        processor.integration = MagicMock()
        processor.integration.create_check_run.return_value = 1, {}

        processor.process()

        mock_complete_check_run.assert_called_once_with(
            conclusion="success", output={}, details_url=ANY, old_external_data={}
        )

    @parameterized.expand(
        [
            (True, ProcessPullRequestTask.MESSAGE_CODE_OK),
            (False, ProcessPullRequestTask.MESSAGE_CODE_NOT_OK),
        ]
    )
    def test_check_run_message(self, pr_pass, expected_message):
        processor = ProcessPullRequestTask()

        returned_message = processor.get_check_run_message(pr_pass)
        self.assertEqual(returned_message, expected_message)

    @patch("api.tasks.ProcessPullRequestTask.count_files_lines")
    def test_get_analysis_queue_url_debug(self, mock_count_files_lines):
        with self.settings(DEBUG=True):
            processor = ProcessPullRequestTask()
            result = processor.get_analysis_queue_url("repository_path", ["file1", "file2"])
            self.assertIsNone(result)
            mock_count_files_lines.assert_not_called()

    @parameterized.expand(
        [
            (0, "small"),
            (settings.QUEUE_NUM_LINES_THRESHOLD_SMALL - 1, "small"),
            (settings.QUEUE_NUM_LINES_THRESHOLD_SMALL, "medium"),
            (settings.QUEUE_NUM_LINES_THRESHOLD_MEDIUM - 1, "medium"),
            (settings.QUEUE_NUM_LINES_THRESHOLD_MEDIUM, "large"),
            (settings.QUEUE_NUM_LINES_THRESHOLD_MEDIUM + 1, "large"),
        ]
    )
    @patch("api.tasks.ProcessPullRequestTask.count_files_lines")
    def test_get_analysis_queue_url(self, num_lines, expected_queue_url, mock_count_files_lines):
        with self.settings(
            DEBUG=False,
            SQS_QUEUE_URL_SMALL="small",
            SQS_QUEUE_URL_MEDIUM="medium",
            SQS_QUEUE_URL_LARGE="large",
        ):
            mock_count_files_lines.return_value = num_lines
            processor = ProcessPullRequestTask()
            queue_url = processor.get_analysis_queue_url("repository_path", ["file1", "file2"])
            self.assertEqual(queue_url, expected_queue_url)

    @patch("api.tasks.ProcessPullRequestTask.queue_conditions")
    @patch("api.tasks.ProcessPullRequestTask.count_files_lines")
    def test_get_analysis_queue_url_no_condition(self, mock_count_files_lines, mock_queue_conditions):
        with self.settings(DEBUG=False):
            mock_count_files_lines.return_value = 1
            processor = ProcessPullRequestTask()
            mock_queue_conditions.return_value = [(lambda num_files: num_files < 0, "no_match")]
            result = processor.get_analysis_queue_url("repository_path", ["file1", "file2"])
            self.assertIsNone(result)

    @patch("time.sleep", return_value=None)
    @patch("api.tasks.ProcessPullRequestTask.is_analysis_complete", return_value=True)
    def test_check_remote_analysis_status_success(self, mock_is_analysis_complete, mock_sleep):
        procssor = ProcessPullRequestTask()
        self.assertTrue(procssor.check_remote_analysis_status("dummy_repository_path"))
        mock_sleep.assert_called_once()
        mock_is_analysis_complete.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch("api.tasks.ProcessPullRequestTask.is_analysis_complete")
    def test_check_remote_analysis_status_soft_max_time(self, mock_is_analysis_complete, mock_sleep):
        max_attempts = 4
        mock_is_analysis_complete.side_effect = [False] * max_attempts + [True]

        with self.settings(REMOTE_ANALYSIS_CHECK_INTERVAL=1, REMOTE_ANALYSIS_SOFT_MAX_TIME=max_attempts):
            processor = ProcessPullRequestTask()
            processor.integration = MagicMock()
            self.assertTrue(processor.check_remote_analysis_status("dummy_repository_path"))
            processor.integration.update_check_run.assert_called_with(
                processor.data,
                processor.check_run_id,
                output={
                    "title": processor.TITLE_STILL_RUNNING,
                    "summary": processor.SUMMARY_STILL_RUNNING,
                },
            )
            self.assertEqual(mock_sleep.call_count, max_attempts + 1)
            self.assertEqual(mock_is_analysis_complete.call_count, max_attempts + 1)

    @patch("time.sleep", return_value=None)
    @patch("api.tasks.ProcessPullRequestTask.is_analysis_complete", return_value=False)
    def test_check_remote_analysis_status_timeout_error(self, mock_is_analysis_complete, mock_sleep):
        max_attempts = 10
        with self.settings(
            REMOTE_ANALYSIS_CHECK_INTERVAL=1,
            REMOTE_ANALYSIS_SOFT_MAX_TIME=4,
            REMOTE_ANALYSIS_FAIL_MAX_TIME=max_attempts,
        ):
            processor = ProcessPullRequestTask()
            processor.integration = MagicMock()
            with self.assertRaises(AnalysisTimeoutError):
                processor.check_remote_analysis_status("dummy_repository_path")
                processor.integration.update_check_run.assert_called_once()
                self.assertEqual(mock_sleep.call_count, max_attempts)
                self.assertEqual(mock_is_analysis_complete.call_count, max_attempts)


class ProcessPullRequestTaskGitHubTests(TestCase, ProcessPullRequestTaskMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.integration = GitHubIntegration
        cls.webhooks = cls.get_webhooks_test_data(WebhooksDataTestMixin.WEBHOOK_PROVIDER_GITHUB)
        logging.disable(logging.CRITICAL)


class ProcessPullRequestTaskAzureDevOpsTests(TestCase, ProcessPullRequestTaskMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.integration = AzureDevOpsIntegration
        cls.webhooks = cls.get_webhooks_test_data(WebhooksDataTestMixin.WEBHOOK_PROVIDER_AZURE_DEVOPS)
        logging.disable(logging.CRITICAL)


class ProcessPullRequestTaskBitBucketTests(TestCase, ProcessPullRequestTaskMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.integration = BitBucketIntegration
        cls.webhooks = cls.get_webhooks_test_data(WebhooksDataTestMixin.WEBHOOK_PROVIDER_BITBUCKET)
        logging.disable(logging.CRITICAL)

    def test_process_reopened(self, *args, **kwargs):
        # Bitbucket cannot re-open pull requests.
        pass

import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase
from parameterized import parameterized

from api.tests.mixins import WebhooksDataTestMixin
from compass.integrations.integrations import AzureDevOpsIntegration, PullRequestData


class TestAzureDevOpsIntegration(WebhooksDataTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.webhooks = cls.get_webhooks_test_data(WebhooksDataTestMixin.WEBHOOK_PROVIDER_AZURE_DEVOPS)
        logging.disable(logging.CRITICAL)

    def assert_action(self, action, webhook):
        action_map = {
            WebhooksDataTestMixin.WEBHOOK_OPENED: AzureDevOpsIntegration.WEBHOOK_ACTION_OPENED,
            WebhooksDataTestMixin.WEBHOOK_MERGED: AzureDevOpsIntegration.WEBHOOK_ACTION_CLOSED,
            WebhooksDataTestMixin.WEBHOOK_NOT_MERGED: AzureDevOpsIntegration.WEBHOOK_ACTION_CLOSED,
            WebhooksDataTestMixin.WEBHOOK_REOPENED: AzureDevOpsIntegration.WEBHOOK_ACTION_REOPENED,
            WebhooksDataTestMixin.WEBHOOK_SYNCHRONIZE: AzureDevOpsIntegration.WEBHOOK_ACTION_SYNCHRONIZE,
            "ignore": AzureDevOpsIntegration.WEBHOOK_ACTION_IGNORE,
        }

        self.assertEqual(action, action_map[webhook])

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    def test_parse_data(self, webhook):
        integration = AzureDevOpsIntegration()
        request_data = self.webhooks[webhook]

        data = integration.parse_pull_request_data(request_data)

        resource = request_data["resource"]
        repository = resource["repository"]

        self.assertIsInstance(data, PullRequestData)
        self.assert_action(data.action, webhook)

        self.assertEqual(data.base_url, request_data["resourceContainers"]["account"]["baseUrl"])
        self.assertEqual(data.repo_external_id, repository["id"])
        self.assertEqual(data.project_id, repository["project"]["id"])
        self.assertEqual(data.repo_owner, repository["project"]["name"])
        self.assertEqual(data.repo_name, repository["name"])
        self.assertEqual(data.repo_full_name, f"{repository['project']['name']}/{repository['name']}")
        self.assertEqual(data.head_sha, resource["lastMergeSourceCommit"]["commitId"])
        self.assertEqual(data.base_sha, resource["lastMergeTargetCommit"]["commitId"])
        self.assertEqual(data.pr_number, resource["pullRequestId"])
        self.assertEqual(data.updated_at, request_data["createdDate"])
        self.assertEqual(
            data.merged_at,
            (resource.get("closedDate") if webhook == WebhooksDataTestMixin.WEBHOOK_MERGED else None),
        )
        self.assertEqual(data.merge_commit_sha, resource.get("lastMergeCommit", {}).get("commitId"))

    @patch("compass.integrations.apis.azure_devops_api.AzureDevOpsApi.get_diff_files")
    def test_get_pull_request_files(self, mock_get_diff_files):
        mock_get_diff_files.return_value = [
            {"item": {"path": "/file1.py"}, "changeType": "add"},
            {"item": {"path": "/file2.py"}, "changeType": "edit"},
            {"item": {"path": "/file3.py"}, "changeType": "delete"},
            {"item": {"path": "/file4.py"}, "changeType": "rename"},
            {"item": {"path": "/file5.py"}, "changeType": "delete, sourceRename"},
            {"item": {"path": "/file6.py"}, "changeType": "edit, rename"},
        ]

        expected_output = [
            {"filename": "file1.py", "status": "added"},
            {"filename": "file2.py", "status": "modified"},
            {"filename": "file3.py", "status": "removed"},
            {"filename": "file4.py", "status": "rename"},
            {"filename": "file5.py", "status": "removed, sourceRename"},
            {"filename": "file6.py", "status": "modified, rename"},
        ]

        integration = AzureDevOpsIntegration()
        integration.api = MagicMock()
        integration.api.get_diff_files = mock_get_diff_files

        output = integration.get_pull_request_files(MagicMock())

        self.assertEqual(output, expected_output)

import logging

from django.test import TestCase
from parameterized import parameterized

from api.tests.mixins import WebhooksDataTestMixin
from compass.integrations.integrations import GitHubIntegration, PullRequestData


class TestGitHubIntegration(WebhooksDataTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.webhooks = cls.get_webhooks_test_data(WebhooksDataTestMixin.WEBHOOK_PROVIDER_GITHUB)
        logging.disable(logging.CRITICAL)

    def assert_action(self, action, webhook):
        action_map = {
            WebhooksDataTestMixin.WEBHOOK_OPENED: GitHubIntegration.WEBHOOK_ACTION_OPENED,
            WebhooksDataTestMixin.WEBHOOK_MERGED: GitHubIntegration.WEBHOOK_ACTION_CLOSED,
            WebhooksDataTestMixin.WEBHOOK_NOT_MERGED: GitHubIntegration.WEBHOOK_ACTION_CLOSED,
            WebhooksDataTestMixin.WEBHOOK_REOPENED: GitHubIntegration.WEBHOOK_ACTION_REOPENED,
            WebhooksDataTestMixin.WEBHOOK_SYNCHRONIZE: GitHubIntegration.WEBHOOK_ACTION_SYNCHRONIZE,
        }

        self.assertEqual(action, action_map[webhook])

    @parameterized.expand(WebhooksDataTestMixin.WEBHOOK_LIST)
    def test_parse_data(self, webhook):
        integration = GitHubIntegration()
        request_data = self.webhooks[webhook]

        data = integration.parse_pull_request_data(request_data)

        repository = request_data["repository"]
        pull_request = request_data["pull_request"]

        self.assertIsInstance(data, PullRequestData)
        self.assert_action(data.action, webhook)

        self.assertEqual(data.installation_id, request_data["installation"]["id"])
        self.assertEqual(data.repo_external_id, repository["id"])
        self.assertEqual(data.repo_owner, repository["owner"]["login"])
        self.assertEqual(data.repo_name, repository["name"])
        self.assertEqual(data.repo_full_name, repository["full_name"])
        self.assertEqual(data.head_sha, pull_request["head"]["sha"])
        self.assertEqual(data.base_sha, pull_request["base"]["sha"])
        self.assertEqual(data.pr_number, pull_request["number"])
        self.assertEqual(
            data.updated_at,
            integration.parse_date(pull_request["head"]["repo"]["updated_at"]),
        )
        self.assertEqual(
            data.merged_at,
            (
                integration.parse_date(pull_request["merged_at"])
                if webhook == WebhooksDataTestMixin.WEBHOOK_MERGED
                else None
            ),
        )
        self.assertEqual(data.merge_commit_sha, pull_request["merge_commit_sha"])

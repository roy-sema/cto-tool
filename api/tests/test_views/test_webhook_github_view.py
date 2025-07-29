import json
import logging
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.status import HTTP_200_OK, HTTP_403_FORBIDDEN

from api.views import WebhookGitHubView
from compass.integrations.integrations import GitHubPullRequestData


class WebhookGitHubViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.disable(logging.CRITICAL)

    def request_webhook(self, payload, signature):
        return self.client.post(
            reverse("webhook-github"),
            json.dumps(payload),
            content_type="application/json",
            **{"HTTP_X_HUB_SIGNATURE_256": signature},
        )

    @patch("api.views.webhook_github_view.verify_signature", return_value=True)
    def test_post_with_invalid_action(self, mock_verify_signature):
        response = self.request_webhook({"action": "invalid"}, "valid")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookGitHubView.RESPONSE_UNSUPPORTED_ACTION)
        mock_verify_signature.assert_called_once()

    @patch("api.views.webhook_github_view.verify_signature", return_value=False)
    def test_post_with_invalid_signature(self, mock_verify_signature):
        response = self.request_webhook({"action": WebhookGitHubView.ALLOWED_WEBHOOK_ACTIONS[0]}, "invalid")
        self.assertEqual(response.status_code, HTTP_403_FORBIDDEN)
        mock_verify_signature.assert_called_once()

    @patch("api.views.webhook_github_view.verify_signature", return_value=True)
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    @patch(
        "api.views.webhook_github_view.GitHubIntegration.parse_pull_request_data",
        return_value=GitHubPullRequestData(
            installation_id=123,
            repo_external_id="test",
            action=WebhookGitHubView.ALLOWED_WEBHOOK_ACTIONS[0],
            repo_owner="test",
            repo_name="test",
            repo_full_name="test",
            head_sha="test",
            base_sha="test",
            pr_number="test",
            updated_at=datetime.now(),
        ),
    )
    @patch(
        "api.views.webhook_github_view.GitHubIntegration.init_api",
    )
    def test_post_with_successful_processing(self, mock_init_api, mock_parse_data, mock_run, mock_verify_signature):
        response = self.request_webhook({"action": WebhookGitHubView.ALLOWED_WEBHOOK_ACTIONS[0]}, "valid")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookGitHubView.RESPONSE_SUCCESS)
        mock_verify_signature.assert_called_once()
        mock_parse_data.assert_called_once()
        mock_init_api.assert_called_once()
        mock_run.assert_called_once()

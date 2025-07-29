import json
import logging
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.status import HTTP_200_OK

from api.views import WebhookAzureDevOpsView
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    AzureDevOpsPullRequestData,
)
from mvp.models import DataProviderConnection, Organization


class WebhookAzureDevOpsViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.disable(logging.CRITICAL)

    def request_webhook(self, payload, signature):
        return self.client.post(
            reverse("webhook-azure-devops"),
            json.dumps(payload),
            content_type="application/json",
            **{"HTTP_X_HUB_SIGNATURE_256": signature},
        )

    def test_invalid_action(self):
        response = self.request_webhook({"eventType": "invalid"}, "valid")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookAzureDevOpsView.RESPONSE_UNSUPPORTED_ACTION)

    @patch(
        "compass.integrations.integrations.AzureDevOpsIntegration.parse_pull_request_data",
        return_value=AzureDevOpsPullRequestData(
            project_id="abc123",
            base_url="https://fabrikam.visualstudio.com/DefaultCollection/",
            repo_owner="fabrikam",
            action=AzureDevOpsIntegration.WEBHOOK_ACTION_IGNORE,
            repo_external_id=1,
            repo_name="fabrikam-repo",
            repo_full_name="fabrikam/fabrikam-repo",
            pr_number=1,
            head_sha="head_sha",
            base_sha="base_sha",
            updated_at="2021-10-01T00:00:00Z",
        ),
    )
    @patch("compass.integrations.integrations.AzureDevOpsIntegration.get_personal_access_token")
    @patch("api.views.webhook_azure_devops_view.AzureDevOpsIntegration.init_api")
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    def test_ignore_action(self, mock_run, mock_init_api, mock_get_personal_access_token, mock_parse_data):
        organization = Organization.objects.create(name="TestOrg", status_check_enabled=True)

        connection = DataProviderConnection.objects.create(
            provider=AzureDevOpsIntegration().provider,
            organization=organization,
            data={
                "base_url": "https://fabrikam.visualstudio.com/DefaultCollection/",
                "personal_access_token": "valid_token",
            },
        )

        organization.save()
        connection.save()

        response = self.request_webhook(
            {
                "eventType": WebhookAzureDevOpsView.ALLOWED_WEBHOOK_ACTIONS[0],
                "resourceContainers": {
                    "account": {"baseUrl": "https://fabrikam.visualstudio.com/DefaultCollection/"},
                },
                "resource": {
                    "pullRequestId": 1,
                },
            },
            "valid",
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookAzureDevOpsView.RESPONSE_UNSUPPORTED_ACTION)

        mock_parse_data.assert_called_once()
        mock_get_personal_access_token.assert_not_called()
        mock_init_api.assert_not_called()
        mock_run.assert_not_called()

    @patch("compass.integrations.integrations.AzureDevOpsIntegration.parse_pull_request_data")
    @patch(
        "compass.integrations.integrations.AzureDevOpsIntegration.get_personal_access_token",
        return_value=None,
    )
    @patch("api.views.webhook_azure_devops_view.AzureDevOpsIntegration.init_api")
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    def test_no_connection(self, mock_run, mock_init_api, mock_get_personal_access_token, mock_parse_data):
        response = self.request_webhook(
            {
                "eventType": WebhookAzureDevOpsView.ALLOWED_WEBHOOK_ACTIONS[0],
                "resourceContainers": {
                    "account": {"baseUrl": "https://fabrikam.visualstudio.com/DefaultCollection/"},
                },
                "resource": {
                    "pullRequestId": 1,
                },
            },
            "valid",
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookAzureDevOpsView.CONNECTION_NOT_SET_UP_ERROR)

        mock_parse_data.assert_called_once()
        mock_get_personal_access_token.assert_called_once()
        mock_init_api.assert_not_called()
        mock_run.assert_not_called()

    @patch(
        "compass.integrations.integrations.AzureDevOpsIntegration.parse_pull_request_data",
        return_value=AzureDevOpsPullRequestData(
            project_id="abc123",
            base_url="https://fabrikam.visualstudio.com/DefaultCollection/",
            repo_owner="fabrikam",
            action=WebhookAzureDevOpsView.ALLOWED_WEBHOOK_ACTIONS[0],
            repo_external_id=1,
            repo_name="fabrikam-repo",
            repo_full_name="fabrikam/fabrikam-repo",
            pr_number=1,
            head_sha="head_sha",
            base_sha="base_sha",
            updated_at="2021-10-01T00:00:00Z",
        ),
    )
    @patch(
        "compass.integrations.integrations.AzureDevOpsIntegration.get_personal_access_token",
        return_value="access_token",
    )
    @patch("api.views.webhook_azure_devops_view.AzureDevOpsIntegration.init_api")
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    def test_valid_action(self, mock_run, mock_init_api, mock_get_personal_access_token, mock_parse_data):
        organization = Organization.objects.create(name="TestOrg", status_check_enabled=True)

        connection = DataProviderConnection.objects.create(
            provider=AzureDevOpsIntegration().provider,
            organization=organization,
            data={
                "base_url": "https://fabrikam.visualstudio.com/DefaultCollection/",
                "personal_access_token": "valid_token",
            },
        )

        organization.save()
        connection.save()

        response = self.request_webhook(
            {
                "eventType": WebhookAzureDevOpsView.ALLOWED_WEBHOOK_ACTIONS[0],
                "resourceContainers": {
                    "account": {"baseUrl": "https://fabrikam.visualstudio.com/DefaultCollection/"},
                },
                "resource": {
                    "pullRequestId": 1,
                },
            },
            "valid",
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookAzureDevOpsView.RESPONSE_SUCCESS)

        mock_parse_data.assert_called_once()
        mock_get_personal_access_token.assert_called_once()
        mock_init_api.assert_called_once()
        mock_run.assert_called_once()

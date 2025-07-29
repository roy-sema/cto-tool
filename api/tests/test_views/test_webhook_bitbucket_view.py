import json
import logging
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.status import HTTP_200_OK

from api.views import WebhookBitBucketView
from compass.integrations.integrations import BitBucketIntegration
from mvp.models import DataProviderConnection, Organization


class WebhookBitBucketViewTests(TestCase):
    WEBHOOK_ACTION_COMMENT_CREATED = "pullrequest:comment_created"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.disable(logging.CRITICAL)

    def request_webhook(self, payload=None, webhook_action=None):
        payload = payload or {}
        webhook_action = webhook_action or BitBucketIntegration.WEBHOOK_ACTION_OPENED

        return self.client.post(
            reverse("webhook-bitbucket"),
            json.dumps(payload),
            content_type="application/json",
            headers={BitBucketIntegration.WEBHOOK_EVENT_KEY: webhook_action},
        )

    def test_invalid_action(self):
        response = self.request_webhook(webhook_action="invalid")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookBitBucketView.RESPONSE_UNSUPPORTED_ACTION)

    @patch("api.views.webhook_bitbucket_view.BitBucketIntegration.init_api")
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    def test_ignore_action(self, mock_run, mock_init_api):
        response = self.request_webhook(
            webhook_action=self.WEBHOOK_ACTION_COMMENT_CREATED,
        )
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookBitBucketView.RESPONSE_UNSUPPORTED_ACTION)
        mock_init_api.assert_not_called()
        mock_run.assert_not_called()

    @patch("api.views.webhook_bitbucket_view.verify_signature", return_value=True)
    @patch("api.views.webhook_bitbucket_view.BitBucketIntegration.init_api")
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    def test_no_connection(self, mock_run, mock_init_api, mock_verify_signature):
        response = self.request_webhook(
            {
                "repository": {
                    "uuid": "{38a7213f-01b5-4bc4-bd4c-c7c9d9a40288}",
                    "name": "fabrikam-repo",
                    "full_name": "fabrikam/fabrikam-repo",
                    "workspace": {"slug": "fabrikam"},
                },
                "pullrequest": {
                    "id": 46,
                    "updated_on": "2024-10-18T12:24:19.381088+00:00",
                    "destination": {"commit": {"hash": "be2862d031ec"}},
                    "source": {"commit": {"hash": "1c56e1539c13"}},
                    "merge_commit": None,
                },
                "actor": {},
            },
            webhook_action=BitBucketIntegration.WEBHOOK_ACTION_OPENED,
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(
            response.data,
            WebhookBitBucketView.CONNECTION_NOT_SET_UP_ERROR,
        )
        mock_verify_signature.assert_not_called()
        mock_init_api.assert_not_called()
        mock_run.assert_not_called()

    @patch("api.views.webhook_bitbucket_view.verify_signature", return_value=True)
    @patch("api.views.webhook_bitbucket_view.BitBucketIntegration.init_api")
    @patch("api.tasks.ProcessPullRequestTask.run", return_value=True)
    def test_valid_action(self, mock_run, mock_init_api, mock_verify_signature):
        organization = Organization.objects.create(
            name="TestOrg",
            status_check_enabled=True,
        )
        workspace_id = "fabrikam"
        connection = DataProviderConnection.objects.create(
            provider=BitBucketIntegration().provider,
            organization=organization,
            data={
                "access_token": "<access_token>",
                "refresh_token": "<refresh_token>",
                "workspace": workspace_id,
            },
        )
        organization.save()
        connection.save()

        response = self.request_webhook(
            {
                "repository": {
                    "uuid": "{38a7213f-01b5-4bc4-bd4c-c7c9d9a40288}",
                    "name": "fabrikam-repo",
                    "full_name": f"{workspace_id}/fabrikam-repo",
                    "workspace": {"slug": workspace_id},
                },
                "pullrequest": {
                    "id": 46,
                    "updated_on": "2024-10-18T12:24:19.381088+00:00",
                    "destination": {"commit": {"hash": "be2862d031ec"}},
                    "source": {"commit": {"hash": "1c56e1539c13"}},
                    "merge_commit": None,
                },
                "actor": {},
            },
            webhook_action=BitBucketIntegration.WEBHOOK_ACTION_OPENED,
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, WebhookBitBucketView.RESPONSE_SUCCESS)

        mock_verify_signature.assert_called_once()
        mock_init_api.assert_called_once()
        mock_run.assert_called_once()

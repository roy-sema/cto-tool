import logging

from django.conf import settings
from django.http import HttpResponseForbidden
from rest_framework.response import Response

from api.utils import verify_signature
from compass.integrations.apis import GitHubApiConfig
from compass.integrations.integrations import GitHubIntegration

from .base_webhook_view import BaseWebhookView

logger = logging.getLogger(__name__)


class WebhookGitHubView(BaseWebhookView):
    """
    Webhook endpoint for GitHub PR events
    """

    ALLOWED_WEBHOOK_ACTIONS = [
        GitHubIntegration.WEBHOOK_ACTION_CLOSED,
        GitHubIntegration.WEBHOOK_ACTION_OPENED,
        GitHubIntegration.WEBHOOK_ACTION_SYNCHRONIZE,
        GitHubIntegration.WEBHOOK_ACTION_REOPENED,
    ]

    def get_integration(self):
        return GitHubIntegration()

    def post(self, request, *args, **kwargs):
        request_data = request.data
        action = request_data.get("action")

        request_body = request.raw_body
        signature_header = request.headers.get("x-hub-signature-256")
        secret = settings.GITHUB_APP_WEBHOOK_SECRET

        if not verify_signature(request_body, secret, signature_header):
            return HttpResponseForbidden()

        if action not in self.ALLOWED_WEBHOOK_ACTIONS:
            return Response(self.RESPONSE_UNSUPPORTED_ACTION)

        integration = self.get_integration()
        data = integration.parse_pull_request_data(request_data)
        integration.init_api(GitHubApiConfig(data.installation_id))
        self.process_pull_request_background(data, integration)

        return Response(self.RESPONSE_SUCCESS)

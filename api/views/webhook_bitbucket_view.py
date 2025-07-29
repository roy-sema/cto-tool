import logging

from django.http import HttpResponseForbidden
from rest_framework.response import Response

from api.utils import verify_signature
from compass.integrations.apis import BitBucketApiConfig
from compass.integrations.integrations import BitBucketIntegration

from .base_webhook_view import BaseWebhookView

logger = logging.getLogger(__name__)


class WebhookBitBucketView(BaseWebhookView):
    """
    Webhook endpoint for BitBucket PR events
    """

    CONNECTION_NOT_SET_UP_ERROR = "Can't find the connected organization"

    ALLOWED_WEBHOOK_ACTIONS = [
        BitBucketIntegration.WEBHOOK_ACTION_OPENED,
        BitBucketIntegration.WEBHOOK_ACTION_CLOSED,
        BitBucketIntegration.WEBHOOK_ACTION_REJECTED,
        BitBucketIntegration.WEBHOOK_ACTION_SYNCHRONIZE,
    ]

    def get_integration(self) -> BitBucketIntegration:
        return BitBucketIntegration()

    def post(self, request, *args, **kwargs):
        request_headers = request.headers
        action = request_headers.get(BitBucketIntegration.WEBHOOK_EVENT_KEY)

        if action not in self.ALLOWED_WEBHOOK_ACTIONS:
            return Response(self.RESPONSE_UNSUPPORTED_ACTION)

        request_data = request.data
        request_data["action"] = action

        integration = self.get_integration()
        data = integration.parse_pull_request_data(request_data)
        if not data:
            return Response(self.RESPONSE_ERROR)

        workspace = data.workspace
        payload_body = request.raw_body
        connection = integration.get_workspace_connection(workspace)
        if not connection:
            return Response(self.CONNECTION_NOT_SET_UP_ERROR)

        secret_token = connection.data.get("webhook_secret")
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(payload_body, secret_token, signature_header):
            return HttpResponseForbidden()

        access_token, refresh_token = integration.get_connection_credentials(connection)
        if not access_token or not refresh_token:
            return Response(self.CONNECTION_NOT_SET_UP_ERROR)

        config = BitBucketApiConfig(
            workspace=workspace,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        integration.init_api(config, connection)

        self.process_pull_request_background(data, integration)

        return Response(self.RESPONSE_SUCCESS)

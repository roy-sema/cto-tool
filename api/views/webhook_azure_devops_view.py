import logging

from rest_framework.response import Response

from compass.integrations.apis import AzureDevOpsApiConfig
from compass.integrations.integrations import AzureDevOpsIntegration

from .base_webhook_view import BaseWebhookView

logger = logging.getLogger(__name__)


class WebhookAzureDevOpsView(BaseWebhookView):
    """
    Webhook endpoint for Azure DevOps PR events
    """

    CONNECTION_NOT_SET_UP_ERROR = "Can't find the connected organization"

    ALLOWED_WEBHOOK_ACTIONS = [
        AzureDevOpsIntegration.WEBHOOK_ACTION_OPENED,
        AzureDevOpsIntegration.WEBHOOK_ACTION_SYNCHRONIZE,
    ]

    def get_integration(self) -> AzureDevOpsIntegration:
        return AzureDevOpsIntegration()

    def post(self, request, *args, **kwargs):
        request_data = request.data
        action = request_data.get("eventType")

        if action not in self.ALLOWED_WEBHOOK_ACTIONS:
            return Response(self.RESPONSE_UNSUPPORTED_ACTION)

        integration = self.get_integration()
        data = integration.parse_pull_request_data(request_data)

        if data.action == AzureDevOpsIntegration.WEBHOOK_ACTION_IGNORE:
            return Response(self.RESPONSE_UNSUPPORTED_ACTION)

        token = integration.get_personal_access_token(data.base_url)
        if not token:
            return Response(self.CONNECTION_NOT_SET_UP_ERROR)

        integration.init_api(
            AzureDevOpsApiConfig(
                base_url=data.base_url,
                auth_token=token,
            )
        )
        self.process_pull_request_background(data, integration)

        return Response(self.RESPONSE_SUCCESS)

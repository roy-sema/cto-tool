import json
import logging

import requests

from mvp.models import MessageIntegration, MessageIntegrationServiceChoices

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def send_notification(integration: MessageIntegration, body: str) -> bool:
        """Send a notification using the specified integration."""
        if integration.service == MessageIntegrationServiceChoices.MS_TEAMS:
            NotificationService.send_teams_notification(integration, body)
        else:
            logger.error(f"Unsupported service: {integration.service}")
            return False
        return True

    @staticmethod
    def send_teams_notification(integration: MessageIntegration, body):
        url = integration.data.get("webhook_url")

        payload = {"text": body}
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            logger.info(
                f"Notification sent successfully to {integration.organization.name} via {integration.service}",
                extra={
                    "organization": integration.organization.name,
                    "service": integration.service,
                    "status_code": response.status_code,
                },
            )
        except requests.exceptions.RequestException as e:
            logger.exception(
                "Failed to send notification",
                extra={
                    "organization": integration.organization.name,
                    "service": integration.service,
                    "error": e.response.text if e.response else str(e),
                },
            )
            raise

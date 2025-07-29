import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from sentry_sdk.crons import monitor

from compass.integrations.apis.jira_api import JiraApiConfig, JiraRefreshTokenException
from compass.integrations.integrations import JiraIntegration
from mvp.models import DataProviderConnection, Organization
from mvp.services import EmailService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Verifies whether the Jira connection is still valid. If the connection "
        "is no longer valid, it is marked as disconnected and a notification is "
        "sent to the support team. "
        "This check is necessary because Jira access tokens cannot be refreshed "
        "in certain cases — for example, if the connection is more than 365 days old."
    )

    @monitor(monitor_slug="check_jira_connections_are_valid")
    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

    def handle(self, *args, **options):
        organization_id = options.get("orgid", 0)
        if organization_id:
            organizations = [Organization.objects.get(id=organization_id)]
        else:
            organizations = Organization.objects.filter(contextualization_enabled=True)

        organization_with_broken_connections = []
        for organization in organizations:
            jira_integration = JiraIntegration()
            connection = (
                DataProviderConnection.objects.filter(organization=organization, provider=jira_integration.provider)
                .order_by("created_at")
                .last()
            )
            if not connection:
                logger.info(
                    f"No Jira connection found for {organization.name} org.",
                    extra={
                        "organization_public_id": organization.public_id(),
                        "organization_name": organization.name,
                    },
                )
                continue

            if not connection.is_connected():
                # Doing this, so we don't send multiple emails to support.
                logger.info(
                    f"No Jira connection {organization.name} org has already been disconnected.",
                    extra={
                        "organization_public_id": organization.public_id(),
                        "organization_name": organization.name,
                    },
                )
                continue

            jira_connection_is_valid = self.check_jira_connection_is_valid(jira_integration, connection)
            if jira_connection_is_valid:
                logger.info(
                    f"Jira connection for {organization.name} org is valid.",
                    extra={
                        "organization_public_id": organization.public_id(),
                        "organization_name": organization.name,
                    },
                )
                continue

            JiraIntegration.disconnect(connection)
            organization_with_broken_connections.append(organization)

        if organization_with_broken_connections:
            parsed_orgs = ", ".join(f"{org.name} ({org.id})" for org in organization_with_broken_connections)
            logger.exception(
                "Organizations found with invalid Jira connections",
                extra={
                    "organizations": parsed_orgs,
                },
            )
            email_message = (
                f"The following organizations {parsed_orgs} "
                "could not refresh their Jira tokens. Please ask them to re-connect."
            )
            EmailService.send_email(
                "SIP: Organizations with broken Jira connections.",
                email_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SUPPORT_EMAIL],
            )

    def check_jira_connection_is_valid(self, integration, connection):
        try:
            integration.init_api(
                config=JiraApiConfig(
                    access_token=connection.data.get("access_token"),
                    refresh_token=connection.data.get("refresh_token"),
                    cloud_id=connection.data["cloud_id"],
                ),
                connection=connection,
            )
            return True
        except JiraRefreshTokenException:
            logger.exception(
                "Could not refresh tokens for Jira connection",
                extra={
                    "organization_id": connection.organization.id,
                    "organization_name": connection.organization.name,
                    "connection_id": connection.id,
                },
            )
            return False

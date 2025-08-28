import logging

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from sentry_sdk.crons import monitor

from compass.contextualization.models import DailyMessage
from mvp.models import MessageIntegration, MessageIntegrationServiceChoices
from mvp.services.notification_service import NotificationService
from mvp.utils import get_daily_message_template_context

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate and send the daily message notifications to organizations that set up message integration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgids",
            type=int,
            nargs="+",
            help="Narrow execution just to given organization IDs (space-separated).",
        )
        parser.add_argument("--skip-orgids", type=str, nargs="+", help="Skip orgs (space-separated).")
        parser.add_argument("--service", type=str, help="Service to send notifications through (e.g., 'teams').")

    @monitor(monitor_slug="send_daily_message_notification")
    def handle(self, *args, **options):
        organization_ids = options.get("orgids")
        skip_orgids = options.get("skip_orgids")
        service = options.get("service")

        if service and service not in MessageIntegrationServiceChoices.values:
            logger.error(
                f"Invalid service provided: {service}. Valid services are: {MessageIntegrationServiceChoices.values}"
            )
            return

        if organization_ids:
            message_integrations = MessageIntegration.objects.filter(organization__id__in=organization_ids)
        else:
            message_integrations = MessageIntegration.objects.filter(
                organization__contextualization_enabled=True, enabled=True
            )

        if skip_orgids:
            logger.warning(
                f"Skipping daily message notification for organizations {skip_orgids}",
                extra={"skipped_organization_ids": skip_orgids},
            )
            message_integrations = message_integrations.exclude(organization__id__in=skip_orgids)

        if service:
            message_integrations = message_integrations.filter(service=service)

        notifications_sent_to_orgs = []
        notifications_failed_to_orgs = []
        organizations_with_no_new_commits = []

        logger.info("send daily message notification command started")

        for integration in message_integrations:
            organization = integration.organization

            try:
                daily_message = DailyMessage.objects.get(date=timezone.now().date(), organization=organization)
            except DailyMessage.DoesNotExist:
                daily_message = None

            data = daily_message.raw_json if daily_message else {"last_updated": None}

            context = get_daily_message_template_context(organization, data)
            html_content = render_to_string(
                template_name="mvp/emails/partials/daily_message_header.html", context=context
            )

            try:
                NotificationService.send_notification(integration, body=html_content)
                notifications_sent_to_orgs += [integration.organization.name]
            except Exception:
                # generic exception since we don't know what the service might throw and we don't want to crash
                logger.exception(
                    "Error sending notification",
                    extra={"organization": integration.organization.name, "service": integration.service},
                )
                notifications_failed_to_orgs += [integration.organization.name]
                # TODO consider disabling the integration if it fails

        logger.info(
            "Daily message notification sent to organizations",
            extra={
                "organizations": notifications_sent_to_orgs,
                "organizations_with_no_new_commits": organizations_with_no_new_commits,
                "organizations_with_failed_notifications": notifications_failed_to_orgs,
            },
        )

import logging
from typing import NamedTuple

import sentry_sdk
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from sentry_sdk.crons import monitor

from compass.contextualization.models import (
    DayIntervalChoices,
    MessageFilter,
)
from compass.contextualization.serializers import MessageFilterSerializer
from compass.contextualization.services import DailyMessageService
from mvp.mixins import InstrumentedCommandMixin
from mvp.models import CustomUser, Organization
from mvp.services import (
    ConnectedIntegrationsService,
    ContextualizationDayInterval,
    ContextualizationService,
    EmailService,
)
from mvp.utils import (
    get_daily_message_template_context,
    remove_empty_lines_from_text,
)

logger = logging.getLogger(__name__)


class Email(NamedTuple):
    text_content: str
    html_message: str
    context: dict
    recipient: CustomUser


class Command(InstrumentedCommandMixin, BaseCommand):
    help = (
        "Generate and send the daily message email to users that have the "
        "compass_anomaly_insights_notifications flag set to True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgids",
            type=int,
            nargs="+",
            help="Narrow execution just to given organization IDs (space-separated).",
        )
        parser.add_argument(
            "--skip-orgids",
            type=str,
            nargs="+",
            help="Skips sending daily message email to orgs (space-separated).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the command without sending emails and logs them. Useful for testing.",
        )

    @monitor(monitor_slug="send_daily_message_email")
    def handle(self, *args, **options):
        organization_ids = options.get("orgids")
        skip_orgids = options.get("skip_orgids")
        dry_run = options.get("dry_run", False)

        day = timezone.now().date()

        if organization_ids:
            organizations = Organization.objects.filter(id__in=organization_ids)
        else:
            organizations = Organization.objects.filter(contextualization_enabled=True)

        if skip_orgids:
            logger.warning(
                f"Skipping sending daily message email for organizations {skip_orgids}",
                extra={"skipped_organization_ids": skip_orgids},
            )
            organizations = organizations.exclude(id__in=skip_orgids)

        emails_sent_to_orgs = []
        organizations_with_no_new_commits = []
        organizations_with_no_recipients = []
        organizations_with_errors = []
        successful_user_ids = []
        failed_user_ids = []

        logger.info("send daily message email command started")
        for organization in organizations:
            sentry_sdk.set_context(
                "organization",
                {"id": organization.pk, "name": organization.name},
            )
            recipient_list = CustomUser.objects.filter(
                organizations=organization,
                compass_anomaly_insights_notifications=True,
            )
            if not recipient_list:
                organizations_with_no_recipients.append(organization.name)
                logger.warning(
                    "No recipients found for sending daily message email",
                    extra={"organization": organization.name},
                )
                continue

            has_jira_connection = ConnectedIntegrationsService.is_jira_connected(organization)
            has_git_connection = ConnectedIntegrationsService.is_git_connected(organization)

            if has_git_connection:
                try:
                    new_commits_exist = ContextualizationService.check_commits_exist_for_pipeline_a(
                        organization,
                        ContextualizationDayInterval.ONE_DAY,
                    )
                except Exception:
                    logger.exception(
                        "Failed to check for new commits while sending daily message email",
                        extra={
                            "organization": organization.name,
                            "has_git_connection": has_git_connection,
                            "has_jira_connection": has_jira_connection,
                        },
                    )
                    organizations_with_errors.append(organization.name)
                    continue
            else:
                new_commits_exist = False

            data_exists = DailyMessageService.get_data_exists(day=day, organization=organization)

            has_updates = (has_git_connection and new_commits_exist) or has_jira_connection
            if has_updates and not data_exists:
                organizations_with_errors.append(organization.name)
                logger.error(
                    "Skip sending daily message email for org. Likely a problem with the last contextualization run.",
                    extra={
                        "organization": organization.name,
                        "has_git_connection": has_git_connection,
                        "has_jira_connection": has_jira_connection,
                    },
                )
                continue

            message_filters: dict[str, MessageFilter] = {
                mf.user.id: mf
                for mf in MessageFilter.objects.filter(
                    user__in=recipient_list,
                    organization=organization,
                    day_interval=DayIntervalChoices.ONE_DAY,
                )
            }
            no_commits_message = not has_jira_connection and has_git_connection and not new_commits_exist
            emails = []
            for recipient in recipient_list:
                message_filter = message_filters.get(recipient.id)
                serialized_filters = MessageFilterSerializer(message_filter).data
                filtered_data = DailyMessageService.get_data(day, organization, serialized_filters)

                filtered_data_adjusted = filtered_data or {"last_updated": None}
                no_data_after_filter = data_exists and not filtered_data

                context = get_daily_message_template_context(
                    organization, filtered_data_adjusted, no_commits_message, no_data_after_filter
                )

                text_content = render_to_string(
                    template_name="mvp/emails/daily_message.txt",
                    context=context,
                )
                text_content = remove_empty_lines_from_text(text_content)
                html_message = render_to_string(
                    template_name="mvp/emails/daily_message.html",
                    context=context,
                )
                emails.append(
                    Email(
                        text_content=text_content,
                        html_message=html_message,
                        context=context,
                        recipient=recipient,
                    )
                )
            if new_commits_exist:
                emails_sent_to_orgs.append(organization.name)
            else:
                organizations_with_no_new_commits.append(organization.name)

            email_service = EmailService(
                is_dry_run=dry_run,
            )
            with email_service.get_connection():
                for email in emails:
                    is_successful = email_service.send_email(
                        subject=f"SIP-Daily Message - {organization.name}",
                        message=email.text_content,
                        html_message=email.html_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email.recipient.email],
                    )
                    if is_successful:
                        logger.info(
                            "daily message email is sent to a user",
                            extra={
                                "user_id": email.recipient.id,
                                "organization": organization.name,
                                "context": email.context,
                            },
                        )
                        successful_user_ids.append(email.recipient.id)
                    else:
                        logger.error(
                            "failed to send daily message email to a user",
                            extra={
                                "user_id": email.recipient.id,
                                "organization": organization.name,
                                "context": email.context,
                            },
                        )
                        failed_user_ids.append(email.recipient.id)

        logger.info(
            f"{'[dry-run] ' if dry_run else ''}Daily message email sent to organizations",
            extra={
                "organizations": emails_sent_to_orgs,
                "organizations_with_no_new_commits": organizations_with_no_new_commits,
                "organizations_with_no_recipients": organizations_with_no_recipients,
                "organizations_with_errors": organizations_with_errors,
                "successful_user_ids": successful_user_ids,
                "failed_user_ids": failed_user_ids,
            },
        )

import logging

import sentry_sdk
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone
from sentry_sdk.crons import monitor

from compass.contextualization.models import (
    DailyMessage,
    DayIntervalChoices,
    MessageFilter,
    MessageFilterData,
)
from compass.contextualization.serializers import MessageFilterSerializer
from mvp.models import CustomUser, Organization
from mvp.services import (
    ConnectedIntegrationsService,
    ContextualizationDayInterval,
    ContextualizationService,
    EmailService,
)
from mvp.services.contextualization_message_service import (
    ContextualizationMessageService,
)
from mvp.utils import (
    get_daily_message_template_context,
    remove_empty_lines_from_text,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Generate and send the daily message email to users that have the "
        "compass_anomaly_insights_notifications flag set to True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )
        parser.add_argument(
            "--skip-orgids",
            type=str,
            nargs="+",
            help="Skips sending daily message email to orgs (space-separated).",
        )

    @monitor(monitor_slug="send_daily_message_email")
    def handle(self, *args, **options):
        organization_id = options.get("orgid", 0)
        skip_orgids = options.get("skip_orgids", None)

        if organization_id:
            organizations = [Organization.objects.get(id=organization_id)]
        else:
            organizations = Organization.objects.filter(contextualization_enabled=True)

        if skip_orgids:
            logger.warning(
                f"Skipping sending daily message email for organisations {skip_orgids}",
                extra={"skipped_organization_ids": skip_orgids},
            )
            organizations = organizations.exclude(id__in=skip_orgids)

        emails_sent_to_orgs = []
        organizations_with_no_new_commits = []
        organizations_with_no_recipients = []

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
                new_commits_exist = ContextualizationService.check_commits_exist_for_pipeline_a(
                    organization,
                    ContextualizationDayInterval.ONE_DAY,
                )
            else:
                new_commits_exist = False

            try:
                daily_message = DailyMessage.objects.get(date=timezone.now().date(), organization=organization)
            except DailyMessage.DoesNotExist:
                daily_message = None

            has_updates = (has_git_connection and new_commits_exist) or has_jira_connection
            if has_updates and not daily_message:
                logger.error(
                    "Skip sending daily message email for org. Likely a problem with the last contextualization run.",
                    extra={
                        "organization": organization.name,
                        "has_git_connection": has_git_connection,
                        "has_jira_connection": has_jira_connection,
                    },
                )
                continue

            data = daily_message.raw_json if daily_message else {"last_updated": None}

            message_filters: dict[str, MessageFilter] = {
                mf.user.id: mf
                for mf in MessageFilter.objects.filter(
                    user__in=recipient_list,
                    organization=organization,
                    day_interval=DayIntervalChoices.ONE_DAY,
                )
            }
            text_content_list = []
            html_content_list = []

            no_commits_message = not has_jira_connection and has_git_connection and not new_commits_exist

            for recipient in recipient_list:
                message_filter = message_filters.get(recipient.id)
                serialized_filters = MessageFilterSerializer(message_filter).data
                filter_data = MessageFilterData(
                    significance_levels=serialized_filters.get("significance_levels") or [],
                    repository_groups=serialized_filters.get("repository_groups") or [],
                    ticket_categories=serialized_filters.get("ticket_categories") or [],
                )
                filtered_data = ContextualizationMessageService.get_filtered_daily_message_data(data, filter_data)
                context = get_daily_message_template_context(organization, filtered_data, no_commits_message)

                text_content = render_to_string(
                    template_name="mvp/emails/daily_message.txt",
                    context=context,
                )
                text_content = remove_empty_lines_from_text(text_content)
                text_content_list.append(text_content)

                html_content_list.append(
                    render_to_string(
                        template_name="mvp/emails/daily_message.html",
                        context=context,
                    )
                )
            recipient_list = [recipient.email for recipient in recipient_list if recipient.email]
            EmailService.send_personalized_emails(
                subject=f"SIP-Daily Message - {organization.name}",
                messages=text_content_list,
                html_messages=html_content_list,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
            )
            if new_commits_exist:
                emails_sent_to_orgs.append(organization.name)
            else:
                organizations_with_no_new_commits.append(organization.name)

        logger.info(
            "Daily message email sent to organizations",
            extra={
                "organizations": emails_sent_to_orgs,
                "organizations_with_no_new_commits": organizations_with_no_new_commits,
                "organizations_with_no_recipients": organizations_with_no_recipients,
            },
        )

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from sentry_sdk.crons import monitor

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import CustomUser, Organization
from mvp.services import ContextualizationService, EmailService


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = (
        "Sends compass summary insights via email to users that have the "
        "compass_summary_insights_notifications flag set to True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

    @monitor(monitor_slug="send_compass_summary_insights_emails")
    def handle(self, *args, **options):
        organization_id = options.get("orgid", 0)
        if organization_id:
            organizations = Organization.objects.filter(id=organization_id)
            if not organizations:
                raise CommandError(f'Organization with ID "{organization_id}" does not exist.')
        else:
            organizations = Organization.objects.all()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value)

        emails_sent_to_orgs = []
        for org in organizations:
            users = CustomUser.objects.filter(
                organizations=org,
                compass_summary_insights_notifications=True,
            )
            if not users:
                continue

            justification_email = ContextualizationService.format_justification_for_email(
                organization=org,
                start_date=start_date,
                end_date=end_date,
            )
            if not justification_email:
                self.stdout.write(self.style.WARNING(f"No summary insights found for organization: {org.name}"))
                continue

            emails_sent_to_orgs.append(org.name)
            EmailService.send_email(
                subject=f"{settings.APP_NAME} Summary Insights",
                message=justification_email,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(users.values_list("email", flat=True)),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {settings.APP_NAME} Summary Insights to users in "
                f"organizations: {', '.join(emails_sent_to_orgs) or 'None'}"
            )
        )

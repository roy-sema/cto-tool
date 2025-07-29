import logging

from django.conf import settings
from django.core.management import BaseCommand
from sentry_sdk.crons import monitor

from compass.integrations.integrations import MailChimpIntegration
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin

logger = logging.getLogger(__name__)


class Command(
    SingleInstanceCommandMixin,
    InstrumentedCommandMixin,
    BaseCommand,
):
    help = "Syncs users with Mailchimp audience list."

    @monitor(monitor_slug="sync_users_with_mailchimp")
    def handle(self, *args, **kwargs):
        if not settings.MAILCHIMP_ACTIVE:
            logger.warning("Mailchimp is not active. Skipping syncing users with Mailchimp.")
            return

        MailChimpIntegration().sync_users()

        logger.info("Syncing users with Mailchimp audience list complete.")

import logging

from django.core.management.base import BaseCommand, CommandError
from sentry_sdk import capture_exception, push_scope
from sentry_sdk.crons import monitor

from compass.codebasereports.services import SemaScoreService
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import Organization
from mvp.utils import traceback_on_debug

logger = logging.getLogger(__name__)


class Command(
    SingleInstanceCommandMixin,
    InstrumentedCommandMixin,
    BaseCommand,
):
    help = "Calculates daily Sema score for all organizations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--erase",
            action="store_true",
            help="Erase all existing scores.",
        )

        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

    @monitor(monitor_slug="calculate_scores")
    def handle(self, *args, **options):
        erase = options.get("erase", False)
        organization_id = options.get("orgid", 0)
        if organization_id:
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist as exc:
                raise CommandError(f'Organization with ID "{organization_id}" does not exist.') from exc

        organizations = [organization] if organization_id else Organization.objects.all()

        for organization in organizations:
            self.process_organization(organization, erase)

    def process_organization(self, organization, erase):
        try:
            self._process_organization(organization, erase)
        except Exception as error:
            traceback_on_debug()

            with push_scope() as scope:
                scope.set_extra("organization", organization.name)
                capture_exception(error)

            logger.warning(f'Error calculating scores for "{organization}"')

    def _process_organization(self, organization, erase):
        score_service = SemaScoreService(organization)

        if erase:
            score_service.delete_records()

            logger.info(f'Successfully deleted scores for "{organization}"')

        success = score_service.calculate_daily_scores()

        if success:
            logger.info(f'Successfully calculated scores for "{organization}"')
        else:
            logger.warning(f'No scores calculated for "{organization}"')

import logging

from compass.integrations.integrations import (
    SnykIntegration,
    get_codebase_reports_providers,
)
from mvp.models import DataProviderConnection, ScoreRecord
from mvp.utils import get_days, get_since_until_last_record_months, get_tz_date

from . import SemaScoreCalculator

logger = logging.getLogger(__name__)


class SemaScoreService:
    NUM_MONTHS_HISTORIC = 3

    def __init__(self, organization):
        self.organization = organization
        self.calculator = SemaScoreCalculator(organization)

    def calculate_daily_scores(self):
        last_fetch_date = self.get_most_recent_fetch_date_all_connections()
        if not last_fetch_date:
            logger.info(f'Data fetch pending for "{self.organization}". Skipping calculation')
            return False

        self.delete_records_on_new_connections()

        since, until = self.get_since_until()
        until = min(until, get_tz_date(last_fetch_date))

        # Skip since X 23:59:59 until X+1 00:00:00
        if (until - since).total_seconds() <= 1:
            logger.info(f"Skipping calculation until the end of the day")
            return False

        logger.info(f'Calculating scores for "{self.organization}" since {since} until {until}')

        days = get_days(since, until)

        for day in days:
            self.record_scores(day, *self.calculator.get_scores(day))

        return True

    def record_scores(self, date, sema_score, compliance_score, product_score):
        if sema_score is not None or compliance_score is not None or product_score is not None:
            ScoreRecord.objects.create(
                organization=self.organization,
                compliance_score=compliance_score,
                product_score=product_score,
                sema_score=sema_score,
                date_time=date,
            )

    def delete_records_on_new_connections(self):
        last_record = self.get_last_score_record()
        if not last_record:
            return

        num_connections = self.get_added_connections(last_record.date_time)
        if not num_connections:
            return

        logger.info(f'New connections for "{self.organization}". Deleting previous records.')
        self.delete_records()

    def get_since_until(self):
        """
        From NUM_MONTHS_HISTORIC months ago (first day of monty) until today,
        or from the next day after the last record until today
        """
        return get_since_until_last_record_months(self.get_last_score_record(), self.NUM_MONTHS_HISTORIC)

    def get_last_score_record(self):
        try:
            qs = ScoreRecord.objects.filter(organization=self.organization)
            return qs.latest("date_time")
        except ScoreRecord.DoesNotExist:
            return None

    def get_most_recent_fetch_date_all_connections(self):
        # TODO: remove this when Snyk API access is fixed
        providers = get_codebase_reports_providers()
        snyk = SnykIntegration().provider
        if snyk in providers:
            providers.remove(snyk)

        connections = DataProviderConnection.objects.filter(
            organization=self.organization,
            provider__in=get_codebase_reports_providers(),
            data__isnull=False,
        ).values("last_fetched_at")

        last_fetch_date = None
        for connection in connections:
            if not connection["last_fetched_at"]:
                return None

            if not last_fetch_date or connection["last_fetched_at"] < last_fetch_date:
                last_fetch_date = connection["last_fetched_at"]

        return last_fetch_date

    # TODO: avoid duplication on CaveatsWidget().get_added_connections
    def get_added_connections(self, since):
        return DataProviderConnection.objects.filter(organization=self.organization, created_at__gte=since).count()

    def delete_records(self):
        ScoreRecord.objects.filter(organization=self.organization).delete()

from datetime import datetime, timedelta

from django.test import TestCase

from compass.codebasereports.services import SemaScoreCalculator, SemaScoreService
from mvp.models import Organization, ReferenceMetric, ScoreRecord
from mvp.services import OrganizationSegmentService
from mvp.utils import get_tz_date


class SemaScoreCalculationTests(TestCase):
    def setUp(self):
        # TODO: use fixtures
        self.organization = Organization.objects.create(name="TestOrg")
        segment = OrganizationSegmentService(self.organization).segment()

        multiplier = 0.5
        calculator = SemaScoreCalculator(self.organization)
        percentiles = [0, 25, 50, 75, 100]

        for metric in calculator.metrics:
            for percentile in percentiles:
                ReferenceMetric.objects.create(
                    metric=metric,
                    percentile=percentile,
                    segment=segment,
                    value=multiplier * percentile,
                )

        num_metrics = ReferenceMetric.objects.count()
        self.assertEqual(num_metrics, len(calculator.metrics) * len(percentiles))

    def test_task_runs(self):
        SemaScoreService(self.organization).calculate_daily_scores()

        num_records = ScoreRecord.objects.count()
        self.assertEqual(num_records, 0)

    def test_score_record_created(self):
        # TODO: create connections and check num records is > 1
        yesterday = get_tz_date(datetime.utcnow().date() - timedelta(days=1))
        pass

from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Sum

from compass.codebasereports.widgets import (
    CodacyWidget,
    IRadarWidget,
    SnykWidget,
    TeamWidget,
)
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
    SnykIssueSeverity,
    SnykLicenseSeverity,
)
from mvp.models import DataProviderMemberProjectRecord, ReferenceMetric
from mvp.services import OrganizationSegmentService
from mvp.utils import get_months_ago

from .trend_change_calculator import TrendChangeCalculator, TrendChangeConfig


class SemaScoreDataProvider:
    def __init__(self, organization):
        self.organization = organization
        self._commits_per_developer = {}
        self._widgets = {}

        self.until = datetime.utcnow().date()
        self.since = self.until - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS)

    def get_reference_metrics(self):
        """
        Returns the reference metrics to compare to
        """
        return ReferenceMetric.objects.filter(segment=OrganizationSegmentService(self.organization).segment()).values()

    def get_metric_value(self, metric, date):
        return getattr(self, f"get_{metric}_value")(date)

    def get_high_risk_in_file_value(self, date):
        # TODO: when we have other Code Security data providers, we need to choose among them
        return self.get_snyk_issues_value(date, "sast")

    def get_high_risk_cves_value(self, date):
        # TODO: when we have other Code Security data providers, we need to choose among them
        return self.get_snyk_issues_value(date, "cve")

    def get_in_reference_risk_count_value(self, date):
        # TODO: when we have other Open Source data providers, we need to choose among them
        severities = [SnykLicenseSeverity.MEDIUM_HIGH, SnykLicenseSeverity.HIGH]
        return self.get_snyk_issues_value(date, "license", severities=severities)

    def get_snyk_issues_value(self, date, issue_type, severities=[SnykIssueSeverity.HIGH]):
        if "snyk" not in self._widgets:
            self._widgets["snyk"] = SnykWidget(self.organization).get_widgets(self.since, self.until)

        chart = self._widgets["snyk"].get(f"chart_snyk_issues_{issue_type}")
        if not chart:
            return None

        day = date.strftime(SnykWidget.DATE_DAY)

        if not chart:
            return None

        value = 0
        has_value = False
        for index, series in enumerate(chart["series"]):
            if series["name"] not in severities:
                continue

            datum = self.get_chart_day_value(chart, day, series_index=index)
            if datum is not None:
                has_value = True
                value += datum

        return value if has_value else None

    def get_cyber_security_evaluation_value(self, date):
        # TODO: when we have other Cyber Security data providers, we need to choose among them
        if "iradar" not in self._widgets:
            self._widgets["iradar"] = IRadarWidget(self.organization).get_widgets(self.since, self.until)

        chart = self._widgets["iradar"].get("chart_iradar_submodules_with_risk")
        if not chart:
            return None

        day = date.strftime(IRadarWidget.DATE_DAY)

        return self.get_chart_day_value(chart, day) if chart else None

    def get_developers_retention_ratio_value(self, date):
        if "team" not in self._widgets:
            self._widgets["team"] = TeamWidget(self.organization).get_widgets(self.since, self.until)

        chart = self._widgets["team"].get("chart_team_developers_percentage")
        if not chart:
            return None

        day = date.strftime(TeamWidget.DATE_DAY)
        value = self.get_chart_day_value(chart, day)

        return value / 100 if value else 0

    def get_in_house_current_test_ratio_value(self, date):
        # TODO: when we have other Code Quality data providers, we need to choose among them
        if "codacy" not in self._widgets:
            self._widgets["codacy"] = CodacyWidget(self.organization).get_widgets(self.since, self.until)

        chart = self._widgets["codacy"].get("chart_codacy_coverage_percentage")
        if not chart:
            return None

        day = date.strftime(CodacyWidget.DATE_DAY)
        value = self.get_chart_day_value(chart, day)

        return value / 100 if value else 0

    def get_chart_day_value(self, chart, day, series_index=0):
        if not chart or chart.get("no_data"):
            return None

        try:
            index = chart["categories"].index(day)
            return chart["series"][series_index]["data"][index]
        except ValueError:
            return None

    def get_average_developer_activity_evaluation_value(self, date):
        records = self.get_commits_per_developer(date)
        if not records:
            return None

        return TrendChangeCalculator().average_developer_activity(records, TrendChangeConfig())

    def get_commit_analysis_evaluation_value(self, date):
        records = self.get_commits_per_developer(date)
        if not records:
            return None

        return TrendChangeCalculator().commit_analysis(records, TrendChangeConfig())

    def get_developers_and_development_activity_evaluation_value(self, date):
        records = self.get_commits_per_developer(date)
        if not records:
            return None

        return TrendChangeCalculator().developers_and_development_activity(records, TrendChangeConfig())

    def get_commits_per_developer(self, date):
        if date not in self._commits_per_developer:
            self._commits_per_developer[date] = self._get_commits_per_developer(date)

        return self._commits_per_developer[date]

    def _get_commits_per_developer(self, date):
        return (
            DataProviderMemberProjectRecord.objects.filter(
                member__organization=self.organization,
                field__name__in=[
                    AzureDevOpsIntegration.FIELD_COMMIT_COUNT,
                    BitBucketIntegration.FIELD_COMMIT_COUNT,
                    GitHubIntegration.FIELD_COMMIT_COUNT,
                ],
                date_time__gte=get_months_ago(date, TrendChangeCalculator.LAST_NUM_MONTHS),
                date_time__lte=date,
            )
            .values("date_time", "member__external_id")
            .annotate(commits=Sum("value"))
        )

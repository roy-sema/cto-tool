from datetime import timedelta

from django.core.cache import cache

from compass.codebasereports.insights import (
    HighCveBenchmarkInsight,
    HighSastBenchmarkInsight,
)
from compass.codebasereports.widgets import SeverityIssuesWidget
from compass.integrations.integrations import (
    SnykIntegration,
    SnykIssueSeverity,
    SnykIssueType,
)
from mvp.utils import get_tz_date


class SnykWidget(SeverityIssuesWidget):
    CACHE_KEY_TEMPLATE = "snyk_widget_{organization_id}_{since}_{until}"
    CACHE_TIMEOUT = 86400  # 1 day

    RECORD_FIELDS = SnykIntegration.get_issue_count_field_names()

    @property
    def integration(self):
        return SnykIntegration

    @property
    def severity(self):
        return SnykIssueSeverity

    def get_widgets(self, since, until):
        _since = get_tz_date(since)
        _until = get_tz_date(until)
        cache_key = self.get_cache_key(self.organization.id, _since, _until)

        return cache.get_or_set(cache_key, lambda: self._get_widgets(_since, _until), self.CACHE_TIMEOUT)

    def _get_widgets(self, since, until):
        chart_sast, chart_cve, chart_license = self.get_charts(since, until)

        current_high_sast_issues, current_high_cve_issues = self.get_current_issues(chart_sast, chart_cve)

        insight_high_sast, insight_high_cve = self.get_insights(current_high_sast_issues, current_high_cve_issues)

        return {
            "chart_snyk_issues_sast": chart_sast,
            "chart_snyk_issues_cve": chart_cve,
            "chart_snyk_issues_license": chart_license,
            "insight_high_sast": insight_high_sast,
            "insight_high_cve": insight_high_cve,
            "snyk_high_sast_issues": current_high_sast_issues,
        }

    def get_charts(self, since, until):
        # include last day's data
        until_date = until + timedelta(days=1)

        aggregate = self.AGGREGATE_DATE_FORMAT_WEEK if (until - since).days > self.AGGREGATE_WEEK_THRESHOLD else None

        records = self.sanitize_records(self.get_records(self.RECORD_FIELDS, since, until))

        charts = self.get_stacked_charts(
            records,
            since,
            until,
            fill_gaps=True,
            aggregate=aggregate,
            aggregate_strategy=self.AGGREGATE_STRATEGY_LATEST,
        )

        empty_chart = self.generate_no_data_chart(since, until_date, aggregate=aggregate)

        chart_sast = charts.get(SnykIssueType.SAST, None) or empty_chart
        chart_cve = charts.get(SnykIssueType.VULNERABILITY, None) or empty_chart
        chart_license = charts.get(SnykIssueType.LICENSE, None) or empty_chart

        return chart_sast, chart_cve, chart_license

    def get_current_issues(self, chart_sast, chart_cve):
        # On normalize_severity_level() we're combining "high" + "critical" as "high"
        current_high_sast_issues = self.get_current_snyk_issues(chart_sast, SnykIssueSeverity.HIGH)
        current_high_cve_issues = self.get_current_snyk_issues(chart_cve, SnykIssueSeverity.HIGH)
        return current_high_sast_issues, current_high_cve_issues

    def get_insights(self, current_high_sast_issues, current_high_cve_issues):
        insight_high_sast = (
            HighSastBenchmarkInsight().get_insight(current_high_sast_issues, self.organization)
            if current_high_sast_issues is not None
            else None
        )
        insight_high_cve = (
            HighCveBenchmarkInsight().get_insight(current_high_cve_issues, self.organization)
            if current_high_cve_issues is not None
            else None
        )

        return insight_high_sast, insight_high_cve

    def get_current_snyk_issues(self, chart, severity):
        """
        Get the last entry from the stacked chart
        """
        if not chart or chart.get("no_data"):
            return None

        for series in chart["series"]:
            if series["name"] == severity:
                return series["data"][-1]

        return None

    @classmethod
    def get_cache_key(cls, organization_id, since, until):
        return cls.CACHE_KEY_TEMPLATE.format(organization_id=organization_id, since=since, until=until)

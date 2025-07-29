from datetime import timedelta

from compass.integrations.integrations import (
    IRadarIntegration,
    IRadarIssueSeverity,
    IRadarIssueType,
)
from mvp.utils import get_tz_date

from .severity_issues_widget import SeverityIssuesWidget


class IRadarWidget(SeverityIssuesWidget):
    CHART_KEY_SUBMODULES_WITH_RISK = "submodules_with_risk"

    RECORD_FIELDS = [
        *IRadarIntegration.get_issue_count_field_names(),
        *IRadarIntegration.get_total_issues_field_names(),
    ]

    @property
    def integration(self):
        return IRadarIntegration

    @property
    def severity(self):
        return IRadarIssueSeverity

    def get_widgets(self, since, until):
        chart_cve, chart_submodules = self.get_charts(get_tz_date(since), get_tz_date(until))

        return {
            "chart_iradar_issues_cve": chart_cve,
            "chart_iradar_submodules_with_risk": chart_submodules,
            "iradar_submodules_difference": self.get_submodules_difference(chart_submodules),
        }

    def get_charts(self, since, until):
        # include last day's data
        until_date = until + timedelta(days=1)

        aggregate = self.AGGREGATE_DATE_FORMAT_WEEK if (until - since).days > self.AGGREGATE_WEEK_THRESHOLD else None

        records = self.sanitize_records(self.get_records(self.RECORD_FIELDS, since, until_date))

        charts = self.group_submodules_with_risk(
            self.get_stacked_charts(
                records,
                since,
                until,
                fill_gaps=True,
                aggregate=aggregate,
                aggregate_strategy=self.AGGREGATE_STRATEGY_LATEST,
            )
        )

        empty_chart = self.generate_no_data_chart(since, until_date, aggregate=aggregate)

        chart_cve = charts.get(IRadarIssueType.CVE, None) or empty_chart
        chart_submodules = charts.get(self.CHART_KEY_SUBMODULES_WITH_RISK, None) or empty_chart

        return chart_cve, chart_submodules

    def get_fill_charts_field_names(self):
        names = super().get_fill_charts_field_names()

        for issue_type in self.integration.DATA_KEYS_MAP.keys():
            names.append(self.integration.get_total_issues_field_name(issue_type))

        return names

    def group_submodules_with_risk(self, charts):
        categories = []
        datapoints = []
        for issue_type in self.integration.DATA_KEYS_MAP.keys():
            field_name = self.integration.get_total_issues_field_name(issue_type)

            if field_name not in charts:
                continue

            chart = charts[field_name]
            if not categories:
                categories = chart["categories"]
                datapoints = [0 for x in range(len(categories))]

            for index, value in enumerate(chart["series"][0]["data"]):
                if value > 1:
                    datapoints[index] += 1

            del charts[field_name]

        charts[self.CHART_KEY_SUBMODULES_WITH_RISK] = {
            "series": [
                {
                    "name": "Sub-Modules with Risk",
                    "data": datapoints,
                }
            ],
            "categories": categories,
        }

        return charts

    def get_submodules_difference(self, chart):
        if not chart:
            return None

        data = chart["series"][0]["data"]
        if len(data) < 8:
            return None

        return {"current": data[-1], "last_week": data[-8]}

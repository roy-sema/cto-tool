from datetime import timedelta

from compass.codebasereports.widgets import ChartWidget
from compass.integrations.integrations import CodacyIntegration, CodacyIssueCategory
from mvp.utils import get_tz_date


class CodacyWidget(ChartWidget):
    FIELD_ISSUES_BY_CATEGORY = "codacy_issues_by_category"

    RECORD_FIELDS = [
        CodacyIntegration.FIELD_COMPLEXITY_TOTAL,
        CodacyIntegration.FIELD_COVERAGE_NUM_FILES_UNCOVERED,
        CodacyIntegration.FIELD_COVERAGE_PERCENTAGE,
        CodacyIntegration.FIELD_DUPLICATION_NUM_LINES,
        *CodacyIntegration.get_issue_category_field_names(),
    ]

    def get_widgets(self, since, until):
        (
            chart_complexity,
            chart_coverage,
            chart_coverage_percentage,
            chart_duplication,
            chart_issues,
        ) = self.get_charts(get_tz_date(since), get_tz_date(until))

        return {
            "chart_codacy_complexity": chart_complexity,
            "chart_codacy_coverage": chart_coverage,
            "chart_codacy_coverage_percentage": chart_coverage_percentage,
            "chart_codacy_duplication": chart_duplication,
            "chart_codacy_issues": chart_issues,
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

        chart_complexity = charts.get(CodacyIntegration.FIELD_COMPLEXITY_TOTAL, None) or empty_chart
        chart_coverage = charts.get(CodacyIntegration.FIELD_COVERAGE_NUM_FILES_UNCOVERED, None) or empty_chart
        chart_coverage_percentage = charts.get(CodacyIntegration.FIELD_COVERAGE_PERCENTAGE, None) or empty_chart
        chart_duplication = charts.get(CodacyIntegration.FIELD_DUPLICATION_NUM_LINES, None) or empty_chart
        chart_issues = charts.get(self.FIELD_ISSUES_BY_CATEGORY, None) or empty_chart

        return (
            chart_complexity,
            chart_coverage,
            chart_coverage_percentage,
            chart_duplication,
            chart_issues,
        )

    def parse_stacked_charts_data(self, charts_data, since, until, aggregate=False):
        return super().parse_stacked_charts_data(self.group_issues(charts_data), since, until, aggregate)

    def group_issues(self, charts):
        """
        Group issues for all projects into one chart for category
        """

        has_records = False
        categories = CodacyIssueCategory.get_all()
        series = {}

        for category in categories:
            field_name = CodacyIntegration.get_issue_category_field_name(category["field"])

            if field_name in charts:
                has_records = True
                series_name = category["name"]

                if series_name not in series:
                    series[series_name] = {}

                for project_name, project_data in charts[field_name].items():
                    for day, value in project_data.items():
                        if day not in series[series_name]:
                            series[series_name][day] = 0

                        series[series_name][day] += value

                del charts[field_name]

        if has_records:
            charts[self.FIELD_ISSUES_BY_CATEGORY] = series

        return charts

from datetime import timedelta

from compass.codebasereports.insights import (
    CommitChangeRateInsight,
    DevelopmentActivityChangeRateInsight,
)
from compass.codebasereports.widgets import GroupSeriesChartWidget
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
)
from mvp.utils import get_tz_date


class ProcessWidget(GroupSeriesChartWidget):
    CHART_SERIES_GROUP = "All repositories"

    FIELD_COMMIT_COUNT = "commit_count"
    FIELD_FILE_CHANGE_COUNT = "file_change_count"

    FIELD_MAP = {
        AzureDevOpsIntegration.FIELD_COMMIT_COUNT: FIELD_COMMIT_COUNT,
        AzureDevOpsIntegration.FIELD_FILE_CHANGE_COUNT: FIELD_FILE_CHANGE_COUNT,
        BitBucketIntegration.FIELD_COMMIT_COUNT: FIELD_COMMIT_COUNT,
        BitBucketIntegration.FIELD_FILE_CHANGE_COUNT: FIELD_FILE_CHANGE_COUNT,
        GitHubIntegration.FIELD_COMMIT_COUNT: FIELD_COMMIT_COUNT,
        GitHubIntegration.FIELD_FILE_CHANGE_COUNT: FIELD_FILE_CHANGE_COUNT,
    }

    RECORD_FIELDS = list(FIELD_MAP.keys())

    def get_widgets(self, since, until):
        chart_process_commits, chart_process_files = self.get_charts(get_tz_date(since), get_tz_date(until))
        insight_commits, insight_files = self.get_insights()

        return {
            "chart_process_files": chart_process_files,
            "chart_process_commits": chart_process_commits,
            "insight_commits": insight_commits,
            "insight_files": insight_files,
        }

    def get_charts(self, since, until):
        # include last day's data
        until_date = until + timedelta(days=1)

        aggregate = self.AGGREGATE_DATE_FORMAT_WEEK if (until - since).days > self.AGGREGATE_WEEK_THRESHOLD else None

        records = self.sanitize_records(self.get_records(self.RECORD_FIELDS, since, until_date))

        charts = self.get_stacked_charts(
            self.group_providers_records(records),
            since,
            until,
            aggregate=aggregate,
        )

        empty_chart = self.generate_no_data_chart(since, until_date, aggregate=aggregate)

        chart_commits = charts.get(self.FIELD_COMMIT_COUNT, None) or empty_chart
        chart_files = charts.get(self.FIELD_FILE_CHANGE_COUNT, None) or empty_chart

        return chart_commits, chart_files

    def group_providers_records(self, records_original):
        records = {}

        for record in records_original:
            field_name = self.FIELD_MAP[record["field__name"]]
            project_id = record["project__id"]
            day = record["date_time"].strftime(self.DATE_DAY)
            key = f"{field_name}_{project_id}_{day}"

            if key not in records:
                records[key] = {**record, "field__name": field_name}
            else:
                records[key]["value"] += record["value"]

        return list(records.values())

    def get_insights(self):
        last_week, today = self.get_since_until(self.DAYS_WEEK)
        previous_week = last_week - timedelta(days=self.DAYS_WEEK)
        records = self.sanitize_records(self.get_records(self.RECORD_FIELDS, previous_week, today))

        insight_commits = None
        insight_files = None
        if records:
            insight_commits = CommitChangeRateInsight().get_insight(records, last_week, today)
            insight_files = DevelopmentActivityChangeRateInsight().get_insight(records, last_week, today)
            starts_with_shows = insight_files["status"].startswith("shows")

            if insight_commits:
                insight_commits["text"] = f"Commit activity in the last {self.DAYS_WEEK} days is"

            if insight_files:
                insight_files["text"] = (
                    f"Development activity in the last {self.DAYS_WEEK} days {('' if starts_with_shows else ' is')}"
                )

        return insight_commits, insight_files

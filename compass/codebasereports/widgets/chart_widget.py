from datetime import datetime, timedelta

import pandas as pd

from compass.codebasereports.widgets import BaseWidget
from mvp.models import DataProviderMemberProjectRecord, DataProviderRecord
from mvp.utils import (
    get_days,
    get_first_day_week,
    get_months,
    get_months_ago,
    get_tz_date,
    get_weeks,
)


class ChartWidget(BaseWidget):
    AGGREGATE_DATE_FORMAT_MONTH = "month"
    AGGREGATE_DATE_FORMAT_WEEK = "week"

    AGGREGATE_STRATEGY_LATEST = "latest"
    AGGREGATE_STRATEGY_SUM = "sum"

    # Aggregate per week if there's more than 14 days of data
    AGGREGATE_WEEK_THRESHOLD = 14

    DATE_DAY = "%Y-%m-%d"
    DATE_MONTH = "%Y-%m"

    DAYS_MONTH = 28
    DAYS_WEEK = 7

    MONTHS_QUARTER = 3
    MONTHS_YEAR = 12

    # how many months to look back for records to fill gaps
    OLD_RECORDS_MONTHS = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_records = None

    def get_since_until(self, days=DAYS_MONTH, months=None, include_today=False):
        now = datetime.utcnow().date()
        until = get_tz_date(now if not include_today else now + timedelta(days=1))
        since = get_tz_date(until - timedelta(days=days) if not months else get_months_ago(until, months))

        return (since, until)

    def get_records(self, field_names, since, until, members=False):
        model = DataProviderRecord
        values = ["field__name", "project__name", "project__id", "value", "date_time"]
        if members:
            model = DataProviderMemberProjectRecord
            values.extend(["member__id", "member__name"])

        return (
            model.objects.select_related("project", "field")
            .filter(
                project__organization=self.organization,
                field__name__in=field_names,
                date_time__gte=since,
                date_time__lt=until,
            )
            .order_by("date_time")
            .values(*values)
        )

    def sanitize_records(self, records):
        """
        Keep the most recent for each project, field, and day
        """
        sanitized_records = {}
        for record in records:
            field_name = record["field__name"]
            project_id = record["project__id"]
            member_id = record.get("member__id")
            day = record["date_time"].strftime(self.DATE_DAY)
            key = f"{field_name}_{project_id}_{day}"
            if member_id:
                key = f"{member_id}_{key}"
            sanitized_records[key] = record

        return list(sanitized_records.values())

    def get_stacked_charts(
        self,
        records,
        since,
        until,
        aggregate=False,
        aggregate_strategy=AGGREGATE_STRATEGY_SUM,
        fill_gaps=False,
    ):
        charts = {}
        for record in records:
            field_name = record["field__name"]
            series_name = record["project__name"]
            date = self.get_aggregate_date(record["date_time"], aggregate)

            if field_name not in charts:
                charts[field_name] = {}

            if series_name not in charts[field_name]:
                charts[field_name][series_name] = {}

            if date not in charts[field_name][series_name]:
                charts[field_name][series_name][date] = record["value"]
            elif aggregate:
                if aggregate_strategy == self.AGGREGATE_STRATEGY_SUM:
                    charts[field_name][series_name][date] += record["value"]
                elif aggregate_strategy == self.AGGREGATE_STRATEGY_LATEST:
                    charts[field_name][series_name][date] = record["value"]
                else:
                    raise ValueError(f"Invalid aggregate strategy: {aggregate_strategy}")

        if fill_gaps and charts:
            charts = self.fill_charts_gaps(charts, since, until)

        return self.parse_stacked_charts_data(charts, since, until, aggregate)

    def parse_stacked_charts_data(self, charts_data, since, until, aggregate=False):
        charts = {}
        categories = self.get_aggregate_categories(since, until, aggregate)

        for field_name, series_data in charts_data.items():
            series = []
            for series_name, project_data in series_data.items():
                datapoints = []
                for category in categories:
                    datapoints.append(project_data.get(category, 0))

                series.append(
                    {
                        "name": series_name,
                        "data": datapoints,
                    }
                )

            charts[field_name] = {
                "series": series,
                "categories": categories,
            }

        return charts

    def get_aggregate_categories(self, since, until, aggregate):
        if not aggregate:
            return get_days(since, until, self.DATE_DAY)

        if aggregate == self.AGGREGATE_DATE_FORMAT_MONTH:
            return get_months(since, until, self.DATE_MONTH)

        if aggregate == self.AGGREGATE_DATE_FORMAT_WEEK:
            return get_weeks(since, until, self.DATE_DAY)

        return get_days(since, until, self.DATE_DAY)

    def get_aggregate_date(self, date, aggregate):
        if not aggregate:
            return date.strftime(self.DATE_DAY)

        if aggregate == self.AGGREGATE_DATE_FORMAT_MONTH:
            return date.strftime(self.DATE_MONTH)

        if aggregate == self.AGGREGATE_DATE_FORMAT_WEEK:
            return get_first_day_week(date).strftime(self.DATE_DAY)

        raise ValueError(f"Invalid aggregate: {aggregate}")

    def get_periods_chart(self, charts, field):
        period_chart = {}
        for period, chart in charts.items():
            if field in chart:
                period_chart[period] = chart[field]

        return period_chart if period_chart else None

    def fill_charts_gaps(self, charts, since, until):
        """
        Some providers don't provide daily data, but when they are scheduled
        or there's a change in the repositories.

        Thus, we will use the data from the previous day when there are
        no data for a given day.
        """
        days = get_days(since, until, self.DATE_DAY)
        first_day = days[0]
        self.preload_old_records(charts.keys())

        for field_name, projects in charts.items():
            for project_name, project_data in projects.items():
                previous_day_value = project_data.get(first_day, self.get_most_recent_value(project_name, field_name))

                for day in days:
                    if day not in project_data:
                        project_data[day] = previous_day_value
                    else:
                        previous_day_value = project_data[day]

                charts[field_name][project_name] = project_data

        return charts

    def get_most_recent_value(self, project_name, field_name):
        key = (field_name, project_name)
        return self._old_records.get(key, 0)

    def preload_old_records(self, field_names):
        if self._old_records is None:
            records = self.get_old_records(field_names)
            if not records:
                self._old_records = {}
                return

            df = (
                pd.DataFrame.from_records(records)
                .sort_values(by="date_time", ascending=False)
                .groupby(["field__name", "project__name"])
                .first()
            )

            self._old_records = df["value"].to_dict()

    def get_old_records(self, field_names):
        since, until = self.get_since_until(self.DAYS_MONTH)
        since_3_months, until = self.get_since_until(self.DAYS_MONTH * (self.OLD_RECORDS_MONTHS + 1))
        return self.sanitize_records(self.get_records(field_names, since_3_months, since))

    def generate_no_data_chart(self, since, until, aggregate=None):
        return {
            "series": [],
            "categories": self.get_aggregate_categories(since, until, aggregate),
            "no_data": True,
        }

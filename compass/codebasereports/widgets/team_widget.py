from datetime import timedelta

from django.db.models import Count

from compass.codebasereports.widgets import GroupSeriesChartWidget
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
)
from mvp.models import DataProviderMember, DataProviderMemberProjectRecord
from mvp.utils import get_tz_date


class TeamWidget(GroupSeriesChartWidget):
    CHART_EXTRA_DATA_DEVELOPERS = "Developers"

    CHART_SERIES_GROUP = "Num developers"
    CHART_SERIES_PERCENTAGE_DEVELOPERS = "% of developers"

    FIELD_ACTIVE_DEVELOPERS = "active_developers"
    FIELD_ACTIVE_DEVELOPERS_PERCENTAGE = "active_developers_percentage"
    FIELD_ACTIVE_DEVELOPERS_LAST_28_DAYS = "active_developers_last_28_days"

    RECORD_FIELDS = [
        AzureDevOpsIntegration.FIELD_COMMIT_COUNT,
        BitBucketIntegration.FIELD_COMMIT_COUNT,
        GitHubIntegration.FIELD_COMMIT_COUNT,
    ]

    def get_widgets(self, since, until):
        chart_developers, chart_developers_percentage = self.get_charts(get_tz_date(since), get_tz_date(until))

        return {
            "chart_team_developers": chart_developers,
            "chart_team_developers_percentage": chart_developers_percentage,
        }

    def get_charts(self, since, until):
        # include last day's data
        until_date = until + timedelta(days=1)

        aggregate = self.AGGREGATE_DATE_FORMAT_WEEK if (until - since).days > self.AGGREGATE_WEEK_THRESHOLD else None

        records = self.sanitize_records(self.get_records(self.RECORD_FIELDS, since, until_date, members=True))

        charts = self.get_members_stacked_charts(
            self.add_records_developers_last_28_days(self.group_developer_records(records)),
            since,
            until_date,
            aggregate=aggregate,
        )

        empty_chart = self.generate_no_data_chart(since, until_date, aggregate=aggregate)

        chart_developers = charts.get(self.FIELD_ACTIVE_DEVELOPERS_LAST_28_DAYS)
        if chart_developers:
            charts[self.FIELD_ACTIVE_DEVELOPERS_PERCENTAGE] = {
                **self.get_developers_percentage_chart(chart_developers),
                "extraData": chart_developers["extraData"],
            }

        chart_commits = charts.get(self.FIELD_ACTIVE_DEVELOPERS_LAST_28_DAYS, None) or empty_chart
        chart_files = charts.get(self.FIELD_ACTIVE_DEVELOPERS_PERCENTAGE, None) or empty_chart

        return chart_commits, chart_files

    def group_developer_records(self, records_original):
        records = {}

        group_projects = False

        projects = set()
        for record in records_original:
            projects.add(record.get("project__name"))

            # Early exit to avoid looping all records
            if len(projects) > self.CHART_MAX_SERIES:
                group_projects = True
                break

        for record in records_original:
            project_id = record["project__id"]
            project_name = record["project__name"]
            member_name = record.get("member__name")
            day = record["date_time"].strftime(self.DATE_DAY)
            key = f"{day}" if group_projects else f"{project_id}_{day}"
            series_name = self.CHART_SERIES_GROUP if group_projects else project_name

            if key not in records:
                records[key] = {
                    # Merge BitBucket and GitHub records
                    "field__name": self.FIELD_ACTIVE_DEVELOPERS,
                    "project__id": project_id,
                    "project__name": series_name,
                    "date_time": record["date_time"],
                    "members": [member_name],
                    "value": 1,
                }
            else:
                records[key]["members"].append(member_name)
                records[key]["value"] += 1

        return list(records.values())

    def add_records_developers_last_28_days(self, records):
        """
        For each day, we want the number of active developers in the last 28 days
        """
        new_records = {}
        project_members = {}
        for record in records:
            project_id = record["project__id"]
            day = record["date_time"].strftime(self.DATE_DAY)

            if project_id not in project_members:
                project_members[project_id] = {}

            if day not in project_members[project_id]:
                project_members[project_id][day] = set(record["members"])
            else:
                project_members[project_id][day].update(record["members"])

            key = f"{project_id}_{day}"

            if key not in new_records:
                new_records[key] = {
                    **record,
                    "field__name": self.FIELD_ACTIVE_DEVELOPERS_LAST_28_DAYS,
                }
            else:
                new_records[key]["members"].extend(record["members"])

            members = set(new_records[key]["members"])

            for num_days in range(1, 28):
                day = (record["date_time"] - timedelta(days=num_days)).strftime(self.DATE_DAY)
                if day in project_members[project_id]:
                    members.update(project_members[project_id][day])

            unique_members = list(members)
            new_records[key]["members"] = unique_members
            new_records[key]["value"] = len(unique_members)

        return records + list(new_records.values())

    def get_members_stacked_charts(self, records, since, until, aggregate):
        charts = {}
        members = {}
        for record in records:
            field_name = record["field__name"]
            series_name = record["project__name"]
            date = self.get_aggregate_date(record["date_time"], aggregate)

            if field_name not in charts:
                charts[field_name] = {}
                members[field_name] = {}

            if series_name not in charts[field_name]:
                charts[field_name][series_name] = {}
                members[field_name][series_name] = {}

            if date not in members:
                members[field_name][series_name][date] = list(set(record["members"]))
            else:
                members[field_name][series_name][date].extend(record["members"])
                members[field_name][series_name][date] = list(set(members[field_name][series_name][date]))

            charts[field_name][series_name][date] = len(members[field_name][series_name][date])

        stacked_charts = self.parse_stacked_charts_data(charts, since, until, aggregate)

        for field_name, chart in stacked_charts.items():
            chart_members = [
                {date: sorted(date_members, key=lambda x: x.lower()) for date, date_members in series.items()}
                for series in members[field_name].values()
            ]

            stacked_charts[field_name] = {
                **chart,
                "extraData": {
                    "name": self.CHART_EXTRA_DATA_DEVELOPERS,
                    "series": chart_members,
                },
            }

        return stacked_charts

    def get_developers_percentage_chart(self, chart):
        if not chart:
            return None

        grouped = self.is_chart_grouped(chart)

        total_developers = self.get_all_time_developers()

        series = []
        for series_data in chart["series"]:
            data = []
            total = total_developers if grouped else self.get_project_all_time_developers(series_data["name"])
            for datum in series_data["data"]:
                data.append(round(datum / total * 100, 1) if datum and total else 0)

            series.append(
                {
                    "name": (self.CHART_SERIES_PERCENTAGE_DEVELOPERS if grouped else series_data["name"]),
                    "data": data,
                }
            )

        return {
            "series": series,
            "categories": chart["categories"],
        }

    def get_all_time_developers(self):
        providers = [
            BitBucketIntegration().provider,
            GitHubIntegration().provider,
        ]
        return DataProviderMember.objects.filter(organization=self.organization, provider__in=providers).count()

    def get_project_all_time_developers(self, project_name):
        return (
            DataProviderMemberProjectRecord.objects.filter(
                project__name=project_name,
                field__name__in=self.RECORD_FIELDS,
            )
            .values("member")
            .annotate(Count("id"))
            .count()
        )

    def is_chart_grouped(self, chart):
        return chart and chart["series"][0]["name"] in [
            self.CHART_SERIES_GROUP,
            self.CHART_SERIES_PERCENTAGE_DEVELOPERS,
        ]

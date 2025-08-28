import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sentry_sdk import capture_message, push_scope

from mvp.models import (
    AITypeChoices,
    Organization,
    Repository,
    RepositoryCommit,
    RepositoryCommitStatusChoices,
)
from mvp.utils import get_days, get_first_day_week, get_whole_decimal, round_half_up

from .rule_service import RuleService

logger = logging.getLogger(__name__)


@dataclass
class ChartSeries:
    name: str
    data: list[int | float]


@dataclass
class ChartData:
    categories: list[str]
    series: list[ChartSeries]
    isPercentage: bool


@dataclass
class Chart:
    id: str
    label: str
    data: ChartData


@dataclass
class AIComposition:
    blended: int | float
    pure: int | float
    overall: int | float


class AICompositionService:
    # Aggregate per week if there's more than 14 days of data
    AGGREGATE_WEEK_THRESHOLD = 14

    DATE_FORMAT_DAY = "%Y-%m-%d"

    FIELD_NAME_TOTAL_NUM_LINES = "code_num_lines"
    FIELD_NAME_OVERALL_NUM_LINES = "code_ai_num_lines"
    FIELD_NAME_BLENDED_NUM_LINES = "code_ai_blended_num_lines"

    FIELDS_LINES_NAMES = [
        FIELD_NAME_TOTAL_NUM_LINES,
        FIELD_NAME_OVERALL_NUM_LINES,
        FIELD_NAME_BLENDED_NUM_LINES,
    ]

    NUM_DECIMALS = 2

    # NOTE: this is the order in which they will be shown in the Dashboard left to right
    SERIES = [
        AITypeChoices.OVERALL,
        AITypeChoices.PURE,
        AITypeChoices.BLENDED,
    ]

    SERIES_DAILY_SUFFIX = "daily"

    SERIES_ID_MAP = {label: id for id, label in AITypeChoices.choices}

    SERIES_DELTA_NAME_OVERALL = AITypeChoices.OVERALL.label
    SERIES_DELTA_NAME_BLENDED = AITypeChoices.BLENDED.label
    SERIES_DELTA_NAME_PURE = AITypeChoices.PURE.label
    SERIES_DELTA_NAME_TOTAL = "Total"

    SERIES_DELTA = [
        SERIES_DELTA_NAME_OVERALL,
        SERIES_DELTA_NAME_BLENDED,
        SERIES_DELTA_NAME_PURE,
        SERIES_DELTA_NAME_TOTAL,
    ]

    def __init__(self, organization: Organization):
        self.organization = organization

    def get_charts(
        self,
        since: datetime,
        until: datetime,
        repositories: list[Repository] | None = None,
        identifier: Optional[str] = "",
        daily_charts: bool = False,
    ) -> tuple[list[Chart], list[Chart]]:
        by_date, dates, _ = self.get_data_by_date_and_repository(
            since, until, repositories, add_previous_date=daily_charts
        )

        if not by_date:
            return [], []

        daily = []
        if daily_charts:
            # remove the extra added day
            dates = dates[1:]

            daily_series = self.get_daily_series(by_date, dates)
            daily = self.format_charts(daily_series, dates, f"{self.SERIES_DAILY_SUFFIX}-{identifier}")

        cumulative_series = self.get_cumulative_series(by_date, dates)
        cumulative = self.format_charts(cumulative_series, dates, identifier)

        return cumulative, daily

    def get_data_by_date_and_repository(
        self,
        since: datetime,
        until: datetime,
        repositories: list[Repository] | None = None,
        add_previous_date=False,
    ) -> tuple[dict, list[str], dict]:
        dates, since_data, until_data, aggregate = self.get_dates(since, until, add_previous_date=add_previous_date)

        repositories = repositories or self.organization.repository_set.all()
        commits = self.get_commits(since_data, until_data, repositories)
        if not commits:
            return {}, dates, {}

        by_repository = self.get_commits_by_repository(commits)

        if aggregate:
            by_repository = self.aggregate_weekly_data(by_repository)

        by_date, by_repository = self.get_commits_by_date(by_repository, dates)

        return by_date, dates, by_repository

    def get_dates(self, since: datetime, until: datetime, add_previous_date=False):
        # include last day's data
        until_data = until + timedelta(days=1)

        # get data from the previous day/week to calculate the difference
        since_data = since
        num_days = (until - since).days
        aggregate = num_days > self.AGGREGATE_WEEK_THRESHOLD
        if add_previous_date:
            since_data = get_first_day_week(since - timedelta(days=7)) if aggregate else since - timedelta(days=1)

        dates = get_days(since_data, until_data, self.DATE_FORMAT_DAY)

        if aggregate:
            dates = sorted({self.get_aggregated_week_date(date) for date in dates})

        return dates, since_data, until_data, aggregate

    def format_charts(self, series, dates, identifier):
        return [
            Chart(
                id=self.get_chart_id(_series.name, identifier),
                label=_series.name,
                data=ChartData(categories=dates, series=[_series], isPercentage=True),
            )
            for _series in series
        ]

    def get_composition(self, charts: list[Chart], previous_value_days=8) -> list:
        if not charts:
            return []

        organization_rules = RuleService.get_organization_rules(self.organization)

        percentages = {}
        for chart in charts:
            values = chart.data.series[0].data
            last_value = values[-1]
            previous_value = values[-previous_value_days] if len(values) >= previous_value_days else 0
            percentages[chart.id] = self.format_ai_values(last_value, previous_value)

        return RuleService.format_ai_percentage_rules(percentages, organization_rules)

    def get_daily_num_lines(
        self,
        since: datetime,
        until: datetime,
        repositories: list[Repository] | None = None,
    ) -> dict:
        by_date, dates, by_repository = self.get_data_by_date_and_repository(
            since, until, repositories, add_previous_date=True
        )

        if not by_date:
            return {}

        # remove the extra added day
        dates = dates[1:]

        _, num_lines = self.calculate_daily_data(by_date, dates)

        return num_lines

    def get_daily_num_lines_by_repository(
        self,
        since: datetime,
        until: datetime,
        repositories: list[Repository] | None = None,
    ) -> dict:
        _, dates, by_repository = self.get_data_by_date_and_repository(
            since, until, repositories, add_previous_date=True
        )

        if not by_repository:
            return {}

        # remove the extra added day
        dates = dates[1:]

        num_lines = {}
        for repository_id, repo_data in by_repository.items():
            _, repo_num_lines = self.calculate_daily_data(repo_data, dates)
            num_lines[repository_id] = repo_num_lines

        return num_lines

    def get_commits_by_repository(self, commits: list[dict]) -> dict:
        """There may be more than one commit per repository per day.

        We'll use the last one to calculate the data for that day.

        Because commits are sorted by date ascending, the last commit will be the most recent one.
        """
        by_repository = {}
        for commit in commits:
            repository_id = commit["repository_id"]
            if repository_id not in by_repository:
                by_repository[repository_id] = {}

            date = commit["date_time"].strftime(self.DATE_FORMAT_DAY)

            by_repository[repository_id][date] = {field: commit[field] for field in self.FIELDS_LINES_NAMES}

        return by_repository

    def aggregate_weekly_data(self, by_repository: dict) -> dict:
        weekly = {}
        for repository_id, values in by_repository.items():
            if repository_id not in weekly:
                weekly[repository_id] = {}

            for date, fields in values.items():
                week_date = self.get_aggregated_week_date(date)

                if week_date not in weekly[repository_id]:
                    weekly[repository_id][week_date] = fields
                else:
                    for field_name, field_value in fields.items():
                        weekly[repository_id][week_date][field_name] += field_value

        return weekly

    def get_commits_by_date(self, by_repository: dict, dates: list[str]) -> tuple[dict, dict]:
        empty_day = dict.fromkeys(self.FIELDS_LINES_NAMES, 0)
        by_date = {date: {**empty_day} for date in dates}
        for lines_by_date in by_repository.values():
            first_date = next(iter(lines_by_date.keys()))
            first_value = next(iter(lines_by_date.values()))
            for date_index, date in enumerate(dates):
                # Empty if date is older than previous day with data
                # Otherwise, get previous day or first day available or empty if there's no data
                if lines_by_date.get(date) is None:
                    lines_by_date[date] = (
                        lines_by_date.get(
                            dates[date_index - 1],
                            first_value or empty_day,
                        )
                        if date >= first_date
                        else empty_day
                    )

                for field in self.FIELDS_LINES_NAMES:
                    by_date[date][field] += lines_by_date[date][field]

        # TODO: by_repository could be used for Repositories view since it's data for each repo
        return by_date, by_repository

    def get_cumulative_series(self, by_date: dict, dates: list[str]) -> list[ChartSeries]:
        series = self.calculate_cumulative_percentages(by_date, dates)

        return [ChartSeries(name=series_name, data=values) for series_name, values in series.items()]

    def calculate_cumulative_percentages(self, by_date: dict, dates: list[str]) -> dict:
        series = {_series.label: [0] * len(dates) for _series in self.SERIES}
        for date, fields in by_date.items():
            if date not in dates or not (total_lines := fields[self.FIELD_NAME_TOTAL_NUM_LINES]):
                continue

            overall = self.get_ai_percentage(
                fields[self.FIELD_NAME_OVERALL_NUM_LINES],
                total_lines,
            )
            blended = self.get_ai_percentage(
                fields[self.FIELD_NAME_BLENDED_NUM_LINES],
                total_lines,
            )

            """
            To avoid rounding issues, ignore data on pure and force it by calculating:

            Pure = Overall - Blended
            """
            pure = round_half_up(overall - blended, self.NUM_DECIMALS)

            date_index = dates.index(date)
            series[AITypeChoices.OVERALL.label][date_index] = overall
            series[AITypeChoices.BLENDED.label][date_index] = blended
            series[AITypeChoices.PURE.label][date_index] = pure

        return series

    def get_daily_series(self, by_date: dict, dates: list[str]) -> list[ChartSeries]:
        percentages, _ = self.calculate_daily_data(by_date, dates)

        return [ChartSeries(name=series_name, data=values) for series_name, values in percentages.items()]

    def calculate_daily_data(self, by_date: dict, dates: list[str]) -> tuple[dict, dict]:
        """Aim to return the total of GenAI code pushed per date, in % and num lines.

        Because we do NOT analyze all commits, we can't get the exact number yet.

        Instead, we approximate this by making a delta of previous day lines, excluding negative values.

        In most cases, the relative error should be small.

        TODO: count the number of lines in all commits that day and calculate the % of GenAI code.
        """
        percentages = {_series.label: [0] * len(dates) for _series in self.SERIES}
        num_lines = {name: [0] * len(dates) for name in self.SERIES_DELTA}
        for date, fields in by_date.items():
            if date not in dates or not (total_lines := fields[self.FIELD_NAME_TOTAL_NUM_LINES]):
                continue

            date_index = dates.index(date)
            previous_fields = by_date.get(dates[date_index - 1], {})

            ai_num_lines = fields[self.FIELD_NAME_OVERALL_NUM_LINES]
            blended_num_lines = fields[self.FIELD_NAME_BLENDED_NUM_LINES]
            self.check_ai_composition(total_lines, ai_num_lines, blended_num_lines, date)

            previous_total_lines = previous_fields.get(self.FIELD_NAME_TOTAL_NUM_LINES, 0)
            previous_ai_num_lines = previous_fields.get(self.FIELD_NAME_OVERALL_NUM_LINES, 0)
            previous_blended_num_lines = previous_fields.get(self.FIELD_NAME_BLENDED_NUM_LINES, 0)

            self.check_ai_composition(
                previous_total_lines,
                previous_ai_num_lines,
                previous_blended_num_lines,
                date,
            )

            # Take into account overwritten lines by adding Blended into Overall, and Overall into Total
            blended_delta = max(0, blended_num_lines - previous_blended_num_lines)
            overall_delta = max(0, ai_num_lines - previous_ai_num_lines) + blended_delta
            total_delta = max(0, total_lines - previous_total_lines) + overall_delta

            overall = self.get_ai_percentage(overall_delta, total_delta)
            blended = self.get_ai_percentage(blended_delta, total_delta)

            """
            To avoid rounding issues, ignore data on pure and force it by calculating:

            Pure = Overall - Blended
            """
            pure = round_half_up(overall - blended, self.NUM_DECIMALS)
            pure_delta = overall_delta - blended_delta

            self.check_min_max_value("overall", overall, date)
            self.check_min_max_value("blended", blended, date)
            self.check_min_max_value("pure", pure, date)

            percentages[AITypeChoices.OVERALL.label][date_index] = overall
            percentages[AITypeChoices.BLENDED.label][date_index] = blended
            percentages[AITypeChoices.PURE.label][date_index] = pure

            num_lines[self.SERIES_DELTA_NAME_OVERALL][date_index] = overall_delta
            num_lines[self.SERIES_DELTA_NAME_BLENDED][date_index] = blended_delta
            num_lines[self.SERIES_DELTA_NAME_PURE][date_index] = pure_delta
            num_lines[self.SERIES_DELTA_NAME_TOTAL][date_index] = total_delta

        return percentages, num_lines

    def check_ai_composition(self, total_lines, ai_num_lines, blended_num_lines, date):
        # This should always be the case
        if ai_num_lines <= total_lines and blended_num_lines <= ai_num_lines:
            return

        message = "AI lines > Total lines" if ai_num_lines > total_lines else "Blended lines > AI lines"
        with push_scope() as scope:
            scope.set_extra("organization", self.organization)
            scope.set_extra("total_lines", total_lines)
            scope.set_extra("ai_num_lines", ai_num_lines)
            scope.set_extra("blended_num_lines", blended_num_lines)
            scope.set_extra("date", date)
            capture_message(message, level="error")
            logger.error(message)

    def check_min_max_value(self, name, value, date, min_value=0, max_value=100):
        # This should always be the case
        if value >= min_value and value <= max_value:
            return

        message = f"'{name}' value ({value}) is out of range {min_value}-{max_value}"
        with push_scope() as scope:
            scope.set_extra("organization", self.organization)
            scope.set_extra("name", name)
            scope.set_extra("value", value)
            scope.set_extra("date", date)
            capture_message(message, level="error")
            logger.error(message)

    def get_commits(
        self,
        since: datetime,
        until: datetime,
        repositories: list[Repository],
    ) -> list[dict]:
        """Fetch commits for a date range, ensuring data propagation.

        The AI Engine does analysis nightly, but a repository may not have commits every day.
        Thus, the last analysis done on a repository propagates until there's a new commit.
        For that reason, we'll fetch the closest commit to the since date.
        """
        commits = list(self.get_date_range_commits(since, until, repositories))

        # Get repositories missing the first date
        first_date = since.strftime(self.DATE_FORMAT_DAY)
        repositories_with_first_date = []
        for commit in commits:
            date = commit["date_time"].strftime(self.DATE_FORMAT_DAY)
            if date != first_date:
                # because commits are ordered by date, if the date changes we don't need to check more commits
                break

            repositories_with_first_date.append(commit["repository_id"])

        missing_data_repository_ids = [
            repository.pk for repository in repositories if repository.pk not in repositories_with_first_date
        ]

        # Get missing data if needed
        if missing_data_repository_ids:
            first_commits = self.get_closest_commits(
                until=since,
                repository_ids=missing_data_repository_ids,
            )
            commits = list(first_commits) + commits

        return commits

    def get_date_range_commits(
        self,
        since: datetime,
        until: datetime,
        repositories: list[Repository],
    ):
        qs = (
            RepositoryCommit.objects.filter(
                repository__organization=self.organization,
                date_time__gte=since,
                date_time__lt=until,
                status=RepositoryCommitStatusChoices.ANALYZED,
                pull_requests__isnull=True,
            )
            .order_by("date_time")
            .values(
                *self.FIELDS_LINES_NAMES,
                "repository_id",
                "date_time",
            )
        )

        if repositories:
            qs = qs.filter(repository__in=repositories)

        return qs.all()

    def get_closest_commits(self, until: datetime, repository_ids: list[int]):
        """Get the most recent commit per repository."""
        qs = (
            RepositoryCommit.objects.filter(
                date_time__lt=until,
                repository__id__in=repository_ids,
                status=RepositoryCommitStatusChoices.ANALYZED,
                pull_requests__isnull=True,
            )
            .order_by("repository", "-date_time")
            .distinct("repository")
            .values(
                *self.FIELDS_LINES_NAMES,
                "repository_id",
                "date_time",
            )
        )

        return qs.all()

    def get_ai_percentage(self, ai_lines, total_lines, num_decimals=NUM_DECIMALS):
        if not total_lines or not ai_lines:
            return 0

        return round_half_up(ai_lines / total_lines * 100, num_decimals)

    def format_ai_values(self, value: float, previous_value: Optional[int | float] = 0):
        whole, decimal = get_whole_decimal(value)
        return {
            "value": value,
            "whole": whole,
            "decimal": decimal,
            "previous_value": previous_value,
        }

    def get_chart_id(self, series_label: str, suffix: Optional[str] = None):
        id = self.SERIES_ID_MAP[series_label]
        return f"{id}-{suffix}" if suffix else id

    def get_aggregated_week_date(self, date: str) -> str:
        return get_first_day_week(datetime.strptime(date, self.DATE_FORMAT_DAY)).strftime(self.DATE_FORMAT_DAY)

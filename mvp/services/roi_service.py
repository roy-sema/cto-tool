from datetime import datetime, timedelta

from mvp.models import Organization, Repository, RepositoryGroup
from mvp.services import AICompositionService
from mvp.utils import get_tz_date


class ROIService:
    OVERALL_PERCENTAGE_PERIOD_DAYS = 13  # 14 days, including today

    @classmethod
    def get_potential_productivity_captured(cls, overall_percentage: float, group: RepositoryGroup) -> float:
        potential_productivity_captured = (
            (overall_percentage / group.max_genai_code_usage_percentage) * 100
            if group.max_genai_code_usage_percentage
            else 0
        )
        return min(potential_productivity_captured, 100)

    @classmethod
    def get_productivity_achievement(cls, overall_percentage: float, group: RepositoryGroup) -> float:
        potential_productivity_captured = cls.get_potential_productivity_captured(overall_percentage, group)
        achievement = (
            group.time_spent_coding_percentage
            * group.potential_productivity_improvement_percentage
            * potential_productivity_captured
            / 10000  # dividing by 10000 to get the percentage for multiplying 2 percentages (100 * 100)
        )
        return min(achievement, 100)

    @classmethod
    def has_total_impact(cls, organization: Organization, group: RepositoryGroup) -> bool:
        """Check if the total impact fields are enabled."""
        avg_dev_annual_work_hours = organization.avg_dev_annual_work_hours
        avg_developer_cost = organization.avg_developer_cost
        num_developers = group.num_developers

        return all([avg_dev_annual_work_hours, avg_developer_cost, num_developers])

    @classmethod
    def get_hours_saved(
        cls,
        overall_percentage: float,
        group: RepositoryGroup,
        organization: Organization,
    ) -> float | None:
        if not cls.has_total_impact(organization, group):
            return None

        productivity_factor = cls.get_productivity_achievement(overall_percentage, group) / 100
        return organization.avg_dev_annual_work_hours * productivity_factor * group.num_developers

    @classmethod
    def get_cost_saved(cls, overall_percentage, group: RepositoryGroup, organization: Organization) -> float | None:
        if not cls.has_total_impact(organization, group):
            return None

        productivity_factor = cls.get_productivity_achievement(overall_percentage, group) / 100
        return organization.avg_developer_cost * productivity_factor * group.num_developers

    @classmethod
    def get_overall_percentage(
        cls,
        group: RepositoryGroup,
        organization: Organization,
        repositories: [Repository] = None,
    ) -> (float, dict):
        """To calculate “the Overall GenAI% of that Repo group for the last 2 weeks”:

        1. Get the number of lines of code for each repository in the group for the last two weeks
        2. Sum all the lines in the period
        3. Obtain the overall percentage
        """
        repositories = repositories or group.repositories.all()
        until = get_tz_date(datetime.utcnow().date())
        since = get_tz_date(until - timedelta(days=cls.OVERALL_PERCENTAGE_PERIOD_DAYS))

        service = AICompositionService(organization)
        daily_data = service.get_daily_num_lines(since, until, repositories)

        deltas = {name: sum(daily_data[name]) for name in AICompositionService.SERIES_DELTA}

        overall_delta = deltas[AICompositionService.SERIES_DELTA_NAME_OVERALL]
        total_delta = deltas[AICompositionService.SERIES_DELTA_NAME_TOTAL]

        overall_percentage = overall_delta / total_delta * 100 if overall_delta and total_delta else 0

        return overall_percentage, {**deltas}

    @classmethod
    def get_tools_cost_saved(cls, group: RepositoryGroup, organization: Organization):
        if not organization.tools_genai_monthly_cost:
            return None

        return organization.tools_genai_monthly_cost * group.num_developers * 12

    @classmethod
    def get_tools_cost_saved_percentage(cls, overall_percentage, group: RepositoryGroup, organization: Organization):
        tools_cost_saved = cls.get_tools_cost_saved(group, organization)
        cost_saved = cls.get_cost_saved(overall_percentage, group, organization)

        if not cost_saved or not tools_cost_saved:
            return None

        return cost_saved / tools_cost_saved * 100

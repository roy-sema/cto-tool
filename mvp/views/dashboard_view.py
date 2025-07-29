from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from compass.integrations.apis import GitHubApi
from compass.integrations.integrations import (
    get_git_provider_integration,
    get_git_providers,
)
from mvp.models import DataProviderConnection, Organization, Repository
from mvp.serializers import ai_composition_serializer, charts_serializer
from mvp.services import AICompositionService, ConnectedIntegrationsService
from mvp.services.roi_service import ROIService
from mvp.utils import round_half_up


class DashboardView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_ai_code_monitor"

    NUM_DECIMALS = 2

    def get(self, request):
        current_org = request.current_organization

        until = timezone.make_aware(datetime.utcnow())
        since = until - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS)

        service = AICompositionService(current_org)
        cumulative_charts, daily_charts = service.get_charts(since=since, until=until, daily_charts=True)
        ai_composition = service.get_composition(cumulative_charts)

        repositories = self.get_repositories_data(current_org)
        first_commit_date = current_org.get_first_commit_date()
        code_attestation_percentages = self.get_code_attestation_percentages(current_org)
        roi_data = self.get_roi_data(current_org)

        integrations = ConnectedIntegrationsService.get_connected_integration_statuses(
            organization=current_org,
            integration_map_keys=ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS,
        )

        updated_at = current_org.get_last_commit_timestamp()

        return render(
            request,
            "mvp/ai_code_monitor/dashboard.html",
            {
                "repositories": repositories,
                "git": self.get_git_data(current_org),
                "cumulative_charts": charts_serializer(cumulative_charts),
                "daily_charts": charts_serializer(daily_charts),
                "ai_composition": ai_composition_serializer(ai_composition),
                "analysis_limits": current_org.analysis_limits(),
                "org_first_date": first_commit_date,
                "code_attestation_percentages": code_attestation_percentages,
                "first_analysis_done": current_org.first_analysis_done,
                "roi_data": roi_data,
                "integrations": integrations,
                "updated_at": updated_at,
            },
        )

    def get_repositories_data(self, organization):
        repositories = organization.repository_set.all()
        return {
            "count": len(repositories),
            "evaluated_percentage": self.get_evaluated_percentage(repositories),
            "has_processed_repositories": repositories.filter(code_num_lines__gt=0).exists(),
        }

    def get_evaluated_percentage(self, repositories):
        lines_total = self.sum_total_num_lines(repositories)
        lines_evaluated = self.sum_code_num_lines(repositories)

        if not lines_total or not lines_evaluated:
            return 0

        return round_half_up(lines_evaluated / lines_total * 100, self.NUM_DECIMALS)

    def get_git_data(self, organization):
        connected = self.is_git_connected(organization)

        github_url = None
        if not connected:
            # TODO: add org to state and encode it
            github_url = GitHubApi.get_installation_url(settings.GITHUB_APP_NAME, "aicm")

        return {
            "connected": connected,
            "github_url": github_url,
        }

    def is_git_connected(self, organization):
        connections = (
            DataProviderConnection.objects.filter(
                organization=organization,
                provider__in=get_git_providers(),
                data__isnull=False,
            )
            .prefetch_related("provider")
            .all()
        )

        for connection in connections:
            integration = get_git_provider_integration(connection.provider)
            if integration.is_connection_connected(connection):
                return True

        return False

    def sum_code_num_lines(self, instances):
        if not instances:
            return 0

        is_dict = isinstance(instances[0], dict)
        return sum([instance["code_num_lines"] if is_dict else instance.code_num_lines for instance in instances])

    def sum_total_num_lines(self, instances):
        return sum([instance.total_num_lines() for instance in instances])

    def get_code_attestation_percentages(self, organization, count=3):
        """
        Gets the code attestation percentages for the organization and its repository groups.

        Always 5 queries !
        - 2: organization.get_attested_num_lines
        - 2: organization.repositorygroup_set.filter
        - 1: Repository.get_attested_num_of_lines_by_sha
        """

        code_attestation_percentages = {
            "Overall": {
                "percentage": (
                    organization.get_attested_num_lines() / org_code_num_lines * 100
                    if (org_code_num_lines := organization.get_code_num_lines())
                    else 0
                ),
                "url": None,
            }
        }

        groups = (
            organization.repositorygroup_set.filter(repository__isnull=False)
            .prefetch_related("repository_set")
            .distinct()
        )

        repositories = [repos for group in groups for repos in group.repository_set.all()]

        num_lines_by_sha = Repository.get_attested_num_of_lines_by_sha(repositories)

        repo_group_attested = {
            group.name: {
                "percentage": (
                    group.get_attested_num_lines(num_lines_by_sha) / group.code_num_lines * 100
                    if group.code_num_lines
                    else 0
                ),
                "url": reverse("repository_groups_dashboard"),
            }
            for group in groups
        }

        lowest_items = sorted(repo_group_attested.items(), key=lambda item: item[1]["percentage"])[:count]
        # reverse to get highest first
        repo_group_attested = dict(lowest_items[::-1])

        code_attestation_percentages.update(repo_group_attested)
        return code_attestation_percentages

    def get_roi_data(self, organization: Organization) -> dict:
        org_hours_saved = None
        org_cost_saved = None
        org_tools_cost_saved = None

        org_potential_productivity_captured = 0
        org_productivity_achievement = 0

        org_debug_data = {}

        repository_groups = organization.repositorygroup_set.all()
        # Summing the developers in all groups was a business decision
        total_developers = sum(group.num_developers or 0 for group in repository_groups)

        if not total_developers:
            return {}

        for group in repository_groups:
            if not group.roi_enabled:
                continue
            overall, debug_data = ROIService.get_overall_percentage(group, organization)
            hours_saved = ROIService.get_hours_saved(overall, group, organization)
            cost_saved = ROIService.get_cost_saved(overall, group, organization)
            tools_cost_saved = ROIService.get_tools_cost_saved(group, organization)

            potential_productivity_captured = (
                ROIService.get_potential_productivity_captured(overall, group)
                * (group.num_developers or 0)
                / total_developers
            )
            productivity_achievement = (
                ROIService.get_productivity_achievement(overall, group) * (group.num_developers or 0) / total_developers
            )

            debug_data = {
                **debug_data,
                "overall_percentage": overall,
                "max_genai_code_usage_percentage": group.max_genai_code_usage_percentage,
                "potential_productivity_improvement_percentage": (group.potential_productivity_improvement_percentage),
                "time_spent_coding_percentage": group.time_spent_coding_percentage,
                "num_developers": group.num_developers,
                "hours_saved": hours_saved,
                "cost_saved": cost_saved,
                "potential_productivity_captured": potential_productivity_captured,
                "productivity_achievement": productivity_achievement,
                "tools_cost_saved": tools_cost_saved,
            }
            org_debug_data[group.name] = debug_data

            # Done this way to maintain the None state if all values are None
            org_hours_saved = org_hours_saved + hours_saved if org_hours_saved else hours_saved
            org_cost_saved = org_cost_saved + cost_saved if org_cost_saved else cost_saved
            org_tools_cost_saved = org_tools_cost_saved + tools_cost_saved if org_tools_cost_saved else tools_cost_saved

            org_potential_productivity_captured += potential_productivity_captured
            org_productivity_achievement += productivity_achievement

        org_tools_cost_saved_percentage = None
        if org_tools_cost_saved is not None and org_cost_saved is not None:
            org_tools_cost_saved_percentage = (
                (org_cost_saved / org_tools_cost_saved) * 100 if org_tools_cost_saved else 0
            )

        return {
            "hours_saved": org_hours_saved,
            "cost_saved": org_cost_saved,
            "potential_productivity_captured": org_potential_productivity_captured,
            "productivity_achievement": org_productivity_achievement,
            "tools_cost_saved_percentage": org_tools_cost_saved_percentage,
            "debug_data": {
                **org_debug_data,
                "total_developers": total_developers,
                "avg_developer_cost": organization.avg_developer_cost,
                "avg_dev_annual_work_hours": organization.avg_dev_annual_work_hours,
                "org_tools_cost_saved": org_tools_cost_saved,
            },
        }

from datetime import datetime, timedelta

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Case, IntegerField, Prefetch, When
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from mvp.mixins import DecodePublicIdMixin
from mvp.models import Repository
from mvp.serializers import (
    RepositoryGroupSerializer,
    RepositorySerializer,
    RuleSerializer,
    charts_serializer,
)
from mvp.services import (
    AICompositionService,
    ConnectedIntegrationsService,
    GroupsAICodeService,
    RuleService,
)
from mvp.services.roi_service import ROIService


class RepositoryGroupView(DecodePublicIdMixin, PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_ai_code_monitor"

    def get(self, request):
        current_org = request.current_organization
        until = parse_date_param(request, "until") or datetime.utcnow().date()
        since = parse_date_param(request, "since") or until - timedelta(days=ROIService.OVERALL_PERCENTAGE_PERIOD_DAYS)

        organization_rules = RuleService.get_organization_rules(current_org)
        repositories = self.get_repositories_data(current_org, organization_rules, since, until)

        integrations = ConnectedIntegrationsService.get_connected_integration_statuses(
            organization=current_org,
            integration_map_keys=ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS,
        )

        return Response({"repositories": repositories, "integrations": integrations})

    def get_repositories_data(
        self,
        organization,
        organization_rules,
        since=None,
        until=None,
    ):
        groups = self.get_grouped_data(
            organization,
            organization_rules,
            with_attestation_data=True,
            since=since,
            until=until,
        )
        ungrouped = self.get_ungrouped_data(organization, with_attestation_data=True, since=since, until=until)
        num_repositories = len(ungrouped["repositories"]) + sum([len(group["repositories"]) for group in groups])

        return {
            "count": num_repositories,
            "groups": groups,
            "ungrouped": ungrouped,
        }

    def get_grouped_data(
        self,
        organization,
        organization_rules,
        with_attestation_data=False,
        since=None,
        until=None,
    ):
        repository_set_prefetch = Prefetch(
            "repository_set",
            queryset=Repository.objects.annotate(
                num_lines=Case(
                    When(code_num_lines=0, then=1),
                    default=0,
                    num_lines=IntegerField(),
                )
            ).order_by("num_lines", "owner", "name"),
        )

        until_commit_prefetch = Prefetch(
            "repository_set__repositorycommit_set",
            queryset=Repository.get_prefetch_commit_before_date(until).queryset,
            to_attr="until_commit",
        )

        groups = organization.repositorygroup_set.prefetch_related(
            "rules",
            "rules__conditions",
            repository_set_prefetch,
            until_commit_prefetch,
        ).order_by("name")

        context = {"with_attestation_data": with_attestation_data, "until": until}

        if with_attestation_data:
            repositories = [repos for group in groups for repos in group.repository_set.all()]
            context["num_lines_by_sha"] = Repository.get_attested_num_of_lines_by_sha(repositories)

        groups_serialized = RepositoryGroupSerializer(groups, many=True, context=context).data

        service = AICompositionService(organization)
        repositories = [repo for group in groups for repo in group.repository_set.all()]

        daily_data = service.get_daily_num_lines_by_repository(since, until, repositories)

        for group, group_serialized in zip(groups, groups_serialized):
            rule_risk_list = self.get_group_rule_risk_list(group, organization_rules)
            group_serialized["rule_risk_list"] = [(RuleSerializer(rule).data, risk) for rule, risk in rule_risk_list]
            repos = group.repository_set.all()
            group_serialized["num_files"] = sum(repo.last_analysis_num_files for repo in repos)

            # TODO: avoid N+1
            group_serialized["charts_cumulative"], group_serialized["charts_daily"] = self.get_repositories_chart(
                organization, repos, group.id, since, until
            )

            # TODO: avoid N+1
            self.add_roi_fields(organization, group, group_serialized, repos)

            range_ai_fields = self.get_date_range_ai_fields(repos, daily_data)

            if until:
                date_ai_fields = range_ai_fields

                attested_num_lines = 0
                num_files = 0
                for repo in group_serialized["repositories"]:
                    commit = repo.get("until_commit") or {}
                    attested_num_lines += commit.get("attested_num_lines") or 0
                    num_files += commit.get("analysis_num_files") or 0
                    repo["date_ai_fields"] = self.get_date_range_ai_fields([repo], daily_data)

                date_ai_fields["attested_num_lines"] = attested_num_lines
                date_ai_fields["num_files"] = num_files

                group_serialized["date_ai_fields"] = date_ai_fields

        return groups_serialized

    def get_ungrouped_data(self, organization, with_attestation_data=False, since=None, until=None):
        repositories = (
            Repository.objects.filter(
                organization=organization,
                last_analysis_num_files__gt=0,
                group__isnull=True,
            )
            .annotate(
                num_lines=Case(
                    When(code_num_lines=0, then=1),
                    default=0,
                    num_lines=IntegerField(),
                )
            )
            .order_by("num_lines", "owner", "name")
            .prefetch_related(Repository.get_prefetch_commit_before_date(until))
        )

        context = {"with_attestation_data": with_attestation_data, "until": until}

        if with_attestation_data:
            context["num_lines_by_sha"] = Repository.get_attested_num_of_lines_by_sha(repositories)

        repositories_serialized = RepositorySerializer(repositories, many=True, context=context).data

        attested_num_lines = 0

        service = AICompositionService(organization)
        daily_data = service.get_daily_num_lines_by_repository(since, until, repositories)
        date_ai_fields = self.get_date_range_ai_fields(repositories, daily_data)

        if until:
            num_files = 0
            attested_num_lines = 0
            for repo in repositories_serialized:
                commit = repo.get("until_commit") or {}
                num_files += commit.get("analysis_num_files") or 0
                attested_num_lines += commit.get("attested_num_lines") or 0
                repo["date_ai_fields"] = self.get_date_range_ai_fields([repo], daily_data)

            date_ai_fields["num_files"] = num_files
            date_ai_fields["attested_num_lines"] = attested_num_lines

        if with_attestation_data:
            attested_num_lines = sum(repo["attested_num_lines"] for repo in repositories_serialized)

        num_files = sum(repo["last_analysis_num_files"] for repo in repositories_serialized)
        charts_cumulative, charts_daily = self.get_repositories_chart(
            organization, repositories, "ungrouped", since, until
        )

        return {
            "name": "Ungrouped",
            "charts_cumulative": charts_cumulative,
            "charts_daily": charts_daily,
            "repositories": repositories_serialized,
            "num_files": num_files,
            "attested_num_lines": attested_num_lines,
            **GroupsAICodeService.calculate_ai_fields(repositories),
            "date_ai_fields": date_ai_fields,
        }

    def get_group_rule_risk_list(self, group, organization_rules):
        return RuleService.get_instance_rules_list(group, list(group.rules.all()) + list(organization_rules))

    def get_repositories_chart(self, organization, repositories, group_id, since, until):
        if not repositories:
            return [], []

        service = AICompositionService(organization)
        charts_cumulative, charts_daily = service.get_charts(
            since, until, repositories, identifier=group_id, daily_charts=True
        )

        return charts_serializer(charts_cumulative), charts_serializer(charts_daily)

    def add_roi_fields(self, organization, group, group_serialized, repositories):
        if not group.roi_enabled or group.max_genai_code_usage_percentage <= 0 or not repositories:
            group_serialized["productivity_achievement"] = 0
            group_serialized["potential_productivity_captured"] = 0
            return

        overall_percentage, debug_data = ROIService.get_overall_percentage(group, organization, repositories)

        group_serialized["potential_productivity_captured"] = ROIService.get_potential_productivity_captured(
            overall_percentage, group
        )

        group_serialized["productivity_achievement"] = ROIService.get_productivity_achievement(
            overall_percentage, group
        )

        group_serialized["hours_saved"] = ROIService.get_hours_saved(overall_percentage, group, organization)

        group_serialized["cost_saved"] = ROIService.get_cost_saved(overall_percentage, group, organization)

        group_serialized["tools_cost_saved_percentage"] = ROIService.get_tools_cost_saved_percentage(
            overall_percentage, group, organization
        )

        # Data for debugging
        group_serialized["debug_data"] = {
            **debug_data,
            "overall_percentage": overall_percentage,
            "max_genai_code_usage_percentage": group.max_genai_code_usage_percentage,
            "potential_productivity_improvement_percentage": (group.potential_productivity_improvement_percentage),
            "time_spent_coding_percentage": group.time_spent_coding_percentage,
            "num_developers": group.num_developers,
            "avg_developer_cost": organization.avg_developer_cost,
            "avg_dev_annual_work_hours": organization.avg_dev_annual_work_hours,
            "tools_cost_saved": ROIService.get_tools_cost_saved(group, organization),
        }

    def get_date_range_ai_fields(self, repositories, daily_data):
        num_lines = 0
        ai_num_lines = 0
        ai_blended_num_lines = 0

        for repo in repositories:
            # this is to support both a list of instances or a list of serialized data
            try:
                repo_pk = repo.pk
            except Exception:
                repo_pk = self.decode_id(repo["public_id"])

            if repo_pk not in daily_data:
                continue

            num_lines += sum(daily_data[repo_pk][AICompositionService.SERIES_DELTA_NAME_TOTAL])
            ai_num_lines += sum(daily_data[repo_pk][AICompositionService.SERIES_DELTA_NAME_OVERALL])
            ai_blended_num_lines += sum(daily_data[repo_pk][AICompositionService.SERIES_DELTA_NAME_BLENDED])

        percentages = GroupsAICodeService.calculate_ai_percentages(num_lines, ai_num_lines, ai_blended_num_lines)

        return {
            "code_num_lines": num_lines,
            **percentages,
        }

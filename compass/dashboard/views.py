import re
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Avg
from django.urls import reverse
from django.utils.text import slugify
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from compass.codebasereports.widgets import SemaScoreWidget
from compass.contextualization.models import AnomalyInsights, DailyMessage, Roadmap, TicketCompleteness
from compass.dashboard.models import GitDiffContext, GitDiffRepositoryGroupInsight
from mvp.models import Organization, Repository
from mvp.services import (
    AICompositionService,
    ConnectedIntegrationsService,
    ContextualizationDayInterval,
    ContextualizationService,
)
from mvp.services.contextualization_message_service import (
    ContextualizationMessageService,
)
from mvp.services.raw_contextualization_service import RawContextualizationService
from mvp.tasks import ImportContextualizationDataTask
from mvp.utils import round_half_up, start_new_thread


class DashboardView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_dashboard"

    DECIMAL_PLACES = 2

    NO_GROUPS_PRODUCT_ID = "all"
    NO_GROUPS_PRODUCT_NAME = "All Code"

    REGEX_CODE_MARK_CODE = r"^([/a-zA-Z0-9_\-]+)(\s|,|.$)?"
    REGEX_CODE_MARK_DIR_PATH = r"^([/a-zA-Z0-9_\-]+)(\s|,|.$)?"
    REGEX_CODE_MARK_FILE_PATH = r"^([/a-zA-Z0-9_\-]+\.[/a-zA-Z0-9_\-]+)(\s|,|.$)?"
    REGEX_CODE_MARK_QUOTES = r"^'([^\s]+)'(\s|,|.$)?"
    REGEX_CODE_MARK_VERSION = r"^(\d+\.\d+\.?\d*)(\s|,|.$)?"

    UNGROUPED_PRODUCT_ID = "other"
    UNGROUPED_PRODUCT_NAME = "Other"

    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        default_until = datetime.utcnow().date()
        default_since = default_until - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value - 1)

        until = parse_date_param(request, "until") or default_until
        since = parse_date_param(request, "since") or default_since

        default_start_date = datetime.combine(default_since, datetime.min.time())
        default_end_date = datetime.combine(default_until, datetime.max.time())

        start_date = datetime.combine(since, datetime.min.time())
        end_date = datetime.combine(until, datetime.max.time())

        is_default_date_range = start_date == default_start_date and end_date == default_end_date

        updated_at = ContextualizationService.get_output_data_timestamp(
            organization, ContextualizationService.OUTPUT_FILENAME_COUNT
        )

        count_data = self.get_count_data(organization, start_date, end_date)

        groups = organization.repositorygroup_set.order_by("name").all()
        repositories = organization.repository_set.all()
        chart, has_ungrouped = self.parse_data_to_chart(count_data, groups, repositories)
        products = self.get_products(groups, has_ungrouped)
        org_first_date = organization.get_first_commit_date()

        # TODO keep this for a while, if we don't need it then we can remove it later
        # if is_default_date_range:
        #     justification_data, _ = ContextualizationService.load_output_data(
        #         organization, ContextualizationService.OUTPUT_FILENAME_JUSTIFICATION
        #     )
        # else:
        #     justification_data = self.get_justification_data(organization, since, until)
        #
        # if justification_data:
        #     justification_data = self.normalize_justification(
        #         justification_data, count_data
        #     )
        #     justification_data = self.enhance_justification(
        #         justification_data, repositories
        #     )

        integrations = ConnectedIntegrationsService.get_connected_integration_statuses(
            organization=organization,
            integration_map_keys=ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS,
        )

        grouped_justification_data, _ = ContextualizationService.load_output_data(
            organization, ContextualizationService.OUTPUT_FILENAME_GROUPED_JUSTIFICATION
        )

        for group_id, data in grouped_justification_data.items():
            data = self.normalize_justification(data, count_data)
            data = self.enhance_justification(data, repositories)
            grouped_justification_data[group_id] = data

        anomaly_insights = ContextualizationService.read_combined_anomaly_script_output(organization)

        repository_map = {repo.public_id(): repo for repo in repositories}

        normalized_anomaly_insights = self.normalize_anomaly_insights(anomaly_insights, repository_map)
        grouped_anomaly_insights = self.group_anomaly_insights_by_repo_group(
            normalized_anomaly_insights, repository_map
        )

        return Response(
            {
                "updated_at": int(updated_at),
                "products": products,
                "chart": chart,
                "org_first_date": org_first_date,
                "default_time_window_days": settings.DEFAULT_TIME_WINDOW_DAYS,
                "integrations": integrations,
                # "justifications": justification_data,
                "grouped_justifications": grouped_justification_data,
                "date_range": (
                    [int(start_date.timestamp()), int(end_date.timestamp())] if end_date.timestamp() else None
                ),
                "repository_groups_url": reverse("repository_groups"),
                "anomaly_insights": grouped_anomaly_insights,
            }
        )

    @classmethod
    def get_count_data(cls, organization, since, until):
        data = {}

        qs = GitDiffContext.get_organization_repositories_stats(organization.id, since, until)

        for record in qs.all():
            group_id = record["repository__group_id"]
            category = record["category"]
            count = record["count"]

            data.setdefault(group_id, {})

            _categories = category.split(" - ")[0].split(",")

            for _category in _categories:
                clean_category = _category.strip()
                data[group_id].setdefault(clean_category, 0)
                data[group_id][clean_category] += count

        return data

    @classmethod
    def get_justification_data(cls, organization, start_date, end_date):
        insights = GitDiffRepositoryGroupInsight.objects.filter(
            organization=organization,
            start_date=start_date,
            end_date=end_date,
            generated=True,
        ).values("category", "percentage", "justification", "examples")

        num_insights = len(insights)
        if not num_insights:
            return None

        categories = {
            insight["category"]: {
                "percentage": insight["percentage"],
                "justification": insight["justification"],
                "examples": insight["examples"],
            }
            for insight in insights
        }

        return {"categories": categories}

    @classmethod
    def normalize_anomaly_insights(cls, anomaly_insights: dict | None, repository_map: dict[str, Repository]):
        if not anomaly_insights:
            return None

        data = {
            "anomaly": anomaly_insights.get("anomaly_insights", []),
            "risk": anomaly_insights.get("risk_insights", []),
        }

        normalized_anomaly_insights = {}
        for anomaly_type, anomalies in data.items():
            for anomaly in anomalies:
                repo_public_id = anomaly["repo"]
                organization = repository_map[repo_public_id].organization
                repo = repository_map[repo_public_id]

                normalized_anomaly_insights.setdefault(repo_public_id, []).append(
                    {
                        "type": anomaly_type,
                        **ContextualizationMessageService.enhance_repo_insight(
                            anomaly,
                            repo_public_id,
                            repo,
                        ),
                    }
                )

        sorted_normalized_anomaly_insights = {}
        for key, value in normalized_anomaly_insights.items():
            sorted_normalized_anomaly_insights[key] = sorted(
                value,
                key=lambda insight: insight["significance_score"] or 0,
                reverse=True,
            )

        return sorted_normalized_anomaly_insights

    @staticmethod
    def group_anomaly_insights_by_repo_group(normalized_anomaly_insights: dict | None, repository_map: dict):
        if not normalized_anomaly_insights:
            return None

        grouped_anomaly_insights = {}
        for (
            repo_public_id,
            repo_anomaly_insights,
        ) in normalized_anomaly_insights.items():
            repo_group = repository_map[repo_public_id].group
            repo_group_name = repo_group.name if repo_group else "ungrouped"
            grouped_anomaly_insights.setdefault(repo_group_name, {}).update(
                {repository_map[repo_public_id].full_name(): repo_anomaly_insights}
            )
        return grouped_anomaly_insights

    @classmethod
    def normalize_justification(cls, justification_data, count_data):
        categories = {}
        total_changes = 0
        changes_by_category = {}
        for categories_data in count_data.values():
            for category, num_changes in categories_data.items():
                category_slug = slugify(category).replace("-", "_")
                categories[category_slug] = category
                changes_by_category.setdefault(category_slug, 0)
                changes_by_category[category_slug] += num_changes
                total_changes += num_changes

        justification = {}
        for category, value in justification_data.get("categories", {}).items():
            num_changes = changes_by_category.get(category, 0)
            if not num_changes:
                continue

            percentage = num_changes / total_changes * 100
            if not percentage:
                continue

            category_slug = slugify(category)
            if category_slug not in categories:
                continue

            category_name = categories[category_slug]
            justification[category_name] = {
                "justification": value.get("justification", ""),
                "examples": value.get("examples", ""),
                "percentage": percentage,
            }

        sorted_justification = {}
        for category in categories.values():
            if category in justification:
                sorted_justification[category] = justification[category]

        return sorted_justification

    def enhance_justification(self, justification_data, repositories):
        repository_names = [name for repo in repositories for name in (repo.name, repo.full_name())]

        for category, value in justification_data.items():
            justification = value.get("justification", "")
            examples = value.get("examples", "")
            value["justification_text"] = justification
            value["examples_text"] = examples
            value["justification"] = self.add_code_marks(justification, repository_names)
            value["examples"] = self.add_code_marks(examples, repository_names)

        return justification_data

    def add_code_marks(self, text, keywords):
        # split on space, comma and brackets.
        words = [x for x in re.split(r"([,\s()])", text) if x]
        for i, word in enumerate(words):
            if word in keywords:
                words[i] = f"`{word}`"
                continue

            words[i] = re.sub(self.REGEX_CODE_MARK_QUOTES, r"`\1`\2", word)
            if words[i] != word:
                continue

            if "." in word:
                words[i] = re.sub(self.REGEX_CODE_MARK_VERSION, r"`\1`\2", word)
                if words[i] != word:
                    continue

                words[i] = re.sub(self.REGEX_CODE_MARK_FILE_PATH, r"`\1`\2", word)
                if words[i] != word:
                    continue

            if "/" in word:
                words[i] = re.sub(self.REGEX_CODE_MARK_DIR_PATH, r"`\1`\2", word)
                if words[i] != word:
                    continue

            if "_" in word:
                words[i] = re.sub(self.REGEX_CODE_MARK_CODE, r"`\1`\2", word)

        return "".join(words)

    def parse_data_to_chart(self, data, groups, repositories):
        ungrouped_repo_ids = [repo.public_id() for repo in repositories if repo.group_id is None]

        if not data or not repositories:
            return {}, bool(ungrouped_repo_ids)

        series_indexes = [group.id for group in groups]

        chart = {
            "categories": [group.name for group in groups],
            "series": {},
        }

        num_series = len(groups)

        if ungrouped_repo_ids:
            num_series += 1
            chart["categories"].append(self.UNGROUPED_PRODUCT_NAME if len(groups) else self.NO_GROUPS_PRODUCT_NAME)

        for group_id, values in data.items():
            series_index = series_indexes.index(group_id) if group_id else num_series - 1

            for change_type, count in values.items():
                if change_type not in chart["series"]:
                    chart["series"][change_type] = {
                        "name": change_type,
                        "data": [0] * num_series,
                    }

                chart["series"][change_type]["data"][series_index] += count

        # Flatten the series dict into a list
        chart["series"] = list(chart["series"].values())

        return self.calculate_percentages(chart), bool(ungrouped_repo_ids)

    def calculate_percentages(self, chart):
        totals = [0] * len(chart["categories"])

        for series in chart["series"]:
            for index, value in enumerate(series["data"]):
                totals[index] += value

        for series in chart["series"]:
            for index, value in enumerate(series["data"]):
                series["data"][index] = (
                    round_half_up(value / totals[index] * 100, self.DECIMAL_PLACES) if totals[index] else 0
                )

        return chart

    def get_products(self, groups, has_ungrouped):
        products = [{"id": group.public_id(), "name": group.name} for group in groups]
        if has_ungrouped:
            products.append(
                {"id": self.UNGROUPED_PRODUCT_ID, "name": self.UNGROUPED_PRODUCT_NAME}
                if len(groups)
                else {
                    "id": self.NO_GROUPS_PRODUCT_ID,
                    "name": self.NO_GROUPS_PRODUCT_NAME,
                }
            )

        return products


class GenerateInsightsView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_dashboard"

    def post(self, request, *args, **kwargs):
        until = parse_date_param(request, "until", payload=True)
        since = parse_date_param(request, "since", payload=True)

        errors = []
        if not since:
            errors.append("'since' is required")
        if not until:
            errors.append("'until' is required")

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        self.process_insights_background(organization=request.current_organization, since=since, until=until)

        return Response({"success": True})

    @start_new_thread
    def process_insights_background(self, organization, since, until):
        has_data = GitDiffRepositoryGroupInsight.objects.filter(
            organization=organization, start_date=since, end_date=until
        ).exists()

        if has_data:
            return

        # Dummy record to avoid multiple generations
        GitDiffRepositoryGroupInsight.objects.create(
            organization=organization,
            start_date=since,
            end_date=until,
            category=DashboardView.NO_GROUPS_PRODUCT_ID,
            generated=False,
        )

        csv_path = ContextualizationService.generate_summary_csv(organization, since, until)

        data = ContextualizationService.execute_pipeline_a_insights(csv_path)

        ImportContextualizationDataTask().import_justification_data(organization, since, until, data=data)


class SIPDashboardView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_dashboard"

    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        until = datetime.utcnow()
        since = until - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS)

        scores = SemaScoreWidget(organization).get_scores()
        service = AICompositionService(organization)
        cumulative_charts, _ = service.get_charts(since=since, until=until, daily_charts=True)
        ai_composition = service.get_composition(cumulative_charts)
        overall = ai_composition[0] if ai_composition else {}
        initiatives_data = Roadmap.get_initiatives_data(organization)

        return Response(
            {
                "overall_ai": {
                    "percentage": overall.get("whole", 0),
                    "color": overall.get("color", None),
                },
                "score": scores.get("sema_score", 0),
                "initiatives": initiatives_data,
            }
        )


class SIPProductRoadmapRadarView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_dashboard"

    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        initiatives_data = Roadmap.get_initiatives_data(organization)
        development_activity, development_activity_updated_at = self.get_development_activity(organization)

        daily_message, daily_message_updated_at = self.get_daily_message(organization)
        raw_results, raw_results_updated_at = self.get_raw_results(organization)

        ticket_completeness, ticket_completeness_updated_at = self.get_ticket_completeness(organization)
        anomaly_insights = self.get_anomaly_insights_updated_at(organization)

        updated_ats = [
            initiatives_data["updated_at"],
            development_activity_updated_at,
            daily_message_updated_at,
            raw_results_updated_at,
            ticket_completeness_updated_at,
            anomaly_insights["updated_at"],
        ]
        updated_ats = [time for time in updated_ats if time]
        updated_at = min(updated_ats) if updated_ats else 0

        integrations = ConnectedIntegrationsService.get_connected_integration_statuses(organization)

        return Response(
            {
                "updated_at": updated_at or None,
                "integrations": integrations,
                "initiatives": initiatives_data,
                "development_activity": development_activity,
                "daily_message": daily_message,
                "raw_results": raw_results,
                "ticket_completeness": ticket_completeness,
                "anomaly_insights": anomaly_insights,
            }
        )

    def get_initiatives_data(self, organization: Organization) -> tuple[dict, float | None]:
        latest_roadmap = Roadmap.latest_by_org(organization)
        if not latest_roadmap:
            initiatives = {"count": 0, "updated_at": None}
            return initiatives, None

        initiatives = {
            "updated_at": latest_roadmap.updated_at.timestamp(),
            "count": latest_roadmap.initiatives.count(),
        }
        return initiatives, latest_roadmap.updated_at.timestamp()

    def get_development_activity(self, organization) -> tuple[dict, float | None]:
        until = datetime.utcnow().date()
        since = until - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value - 1)

        start_date = datetime.combine(since, datetime.min.time())
        end_date = datetime.combine(until, datetime.max.time())

        count_data = DashboardView.get_count_data(organization, start_date, end_date)

        data, updated_at = ContextualizationService.load_output_data(
            organization, ContextualizationService.OUTPUT_FILENAME_JUSTIFICATION
        )
        data = DashboardView.normalize_justification(data, count_data)
        development_activity = {
            "updated_at": updated_at,
            "activities": [
                {
                    "name": activity,
                    "percentage": content.get("percentage"),
                }
                for activity, content in data.items()
            ],
        }

        development_activity["activities"] = sorted(
            development_activity["activities"],
            key=lambda x: x.get("percentage"),
            reverse=True,
        )

        return development_activity, updated_at

    def get_daily_message(self, organization: Organization) -> tuple[dict, float | None]:
        message = DailyMessage.objects.filter(organization=organization).order_by("-updated_at").first()

        daily_message = {
            "updated_at": message.updated_at.timestamp() if message else 0,
        }

        return daily_message, message.updated_at.timestamp() if message else None

    def get_raw_results(self, organization) -> tuple[dict, float | None]:
        results = RawContextualizationService.get_for_day_interval(organization, ContextualizationDayInterval.ONE_DAY)
        raw_results = {
            "updated_at": results.get("updated_at", None),
        }

        return raw_results, results.get("updated_at", None) if results else None

    def get_ticket_completeness(self, organization: Organization) -> tuple[dict, float | None]:
        """Get ticket completeness statistics for organization average."""

        query_set = TicketCompleteness.latest_ticket_data(organization=organization)

        if query_set.exists():
            avg_completeness_score = query_set.aggregate(Avg("completeness_score"))["completeness_score__avg"] or 0
            latest_ticket = query_set.order_by("-updated_at").first()
            updated_at = latest_ticket.updated_at.timestamp() if latest_ticket else None

            ticket_completeness = {
                "updated_at": updated_at,
                "average_score": round(avg_completeness_score),
            }
            return ticket_completeness, updated_at
        else:
            return {"updated_at": None, "average_score": 0}, None

    def get_anomaly_insights_updated_at(self, organization: Organization) -> dict[str, float | None]:
        """Get anomaly insights data updated_at"""
        latest_anomaly = (
            AnomalyInsights.objects.filter(repository__organization=organization).order_by("-updated_at").first()
        )

        if latest_anomaly:
            updated_at = latest_anomaly.updated_at.timestamp()
        else:
            updated_at = None

        return {"updated_at": updated_at}

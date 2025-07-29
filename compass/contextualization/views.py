from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Case, IntegerField, Q, When
from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from compass.contextualization.models import (
    AnomalyInsights,
    DailyMessage,
    DayIntervalChoices,
    MessageFilter,
    MessageFilterData,
    SignificanceLevelChoices,
    TicketCategoryChoices,
    TicketCompleteness,
)
from compass.contextualization.serializers import (
    AnomalyInsightsSerializer,
    MessageFilterSerializer,
    TicketCompletenessSerializer,
    TicketCompletenessTicketSerializer,
)
from mvp.models import RepositoryGroup
from mvp.serializers import RepositoryGroupSimpleSerializer
from mvp.services.contextualization_message_service import (
    ContextualizationMessageService,
)
from mvp.utils import get_daily_message_template_context

DATE_FORMAT = "%Y-%m-%d"


class DailyMessageView(LoginRequiredMixin, APIView):
    def get(self, request, *args, **kwargs):
        date = request.GET.get("date")
        if not date:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        organization = request.current_organization
        daily_message = DailyMessage.objects.filter(organization=organization, date=date).first()

        if not daily_message or not daily_message.raw_json:
            return Response({"date": None, "content": "No message available for the selected date."})

        significance_levels = request.GET.get("significance_levels")
        significance_levels = significance_levels.split(",") if significance_levels else []
        repository_groups = request.GET.get("repository_groups")
        repository_groups = repository_groups.split(",") if repository_groups else []
        ticket_categories = request.GET.get("ticket_categories")
        ticket_categories = ticket_categories.split(",") if ticket_categories else []
        message_filter_data = MessageFilterData(
            significance_levels=significance_levels,
            repository_groups=repository_groups,
            ticket_categories=ticket_categories,
        )
        daily_message_raw_json = ContextualizationMessageService.get_filtered_daily_message_data(
            daily_message.raw_json, message_filter_data
        )

        template_name = (
            "mvp/emails/daily_message.html"
            if request.GET.get("as-email") == "true"
            else "mvp/daily_message/daily_message.html"
        )
        html_content = render_to_string(
            template_name=template_name,
            context=get_daily_message_template_context(organization, daily_message_raw_json),
        )
        return Response({"date": daily_message.date, "content": html_content})


class TicketCompletenessView(LoginRequiredMixin, APIView):
    page_size = 50
    pagination_class = PageNumberPagination

    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        llm_category = request.GET.get("llm_category")
        project_key = request.GET.get("project_key")
        stage = request.GET.get("stage")
        quality_category = request.GET.get("quality_category")

        sort_order = request.GET.get("sort_order", "desc")
        sort_by = request.GET.get("sort_by", "date")

        queryset = TicketCompleteness.latest_ticket_data(organization=organization).select_related("project")
        sort_order = "" if sort_order == "asc" else "-"
        queryset = queryset.order_by(f"{sort_order}{sort_by}")

        filter_options = self.get_filter_options(organization)

        if llm_category:
            queryset = queryset.filter(llm_category=llm_category)
        if project_key:
            queryset = queryset.filter(project__key=project_key)
        if stage:
            queryset = queryset.filter(stage=stage)

        if quality_category:
            queryset = queryset.filter(quality_category=quality_category)

        paginator = self.pagination_class()
        paginator.page_size = self.page_size
        page = paginator.paginate_queryset(queryset, request)
        serializer = TicketCompletenessSerializer(page, many=True)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "results": serializer.data,
            "filter_options": filter_options,
        }

        return Response(response_data)

    def get_filter_options(self, organization):
        llm_categories = (
            TicketCompleteness.latest_ticket_data(organization=organization)
            .values_list("llm_category", flat=True)
            .distinct()
            .order_by("llm_category")
        )

        project_keys = (
            TicketCompleteness.latest_ticket_data(organization=organization)
            .values_list("project__key", flat=True)
            .distinct()
            .order_by("project__key")
        )

        stages = (
            TicketCompleteness.latest_ticket_data(organization=organization)
            .values_list("stage", flat=True)
            .distinct()
            .order_by("stage")
        )

        return {
            "llm_categories": list(llm_categories),
            "project_keys": list(project_keys),
            "stages": list(stages),
        }


class TicketCompletenessTicketView(LoginRequiredMixin, APIView):
    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        ticket_id = request.GET.get("ticket_id")
        ticket_history = list(
            TicketCompleteness.objects.filter(project__organization=organization, ticket_id=ticket_id)
            .order_by("-date")
            .all()
        )

        scores_history = [{"date": t.date.strftime(DATE_FORMAT), "score": t.completeness_score} for t in ticket_history]

        serializer = TicketCompletenessTicketSerializer(ticket_history[0])
        jira_url = ContextualizationMessageService.get_jira_url(organization, ticket_id)

        return Response({"current_data": serializer.data, "scores_history": scores_history, "jira_url": jira_url})


class TicketCompletenessStatisticsView(LoginRequiredMixin, APIView):
    HISTORICAL_DAYS = 7

    def get(self, request, *args, **kwargs):
        organization = request.current_organization
        project_key = request.GET.get("project_key")

        response_data = {}
        dates = [None, (datetime.now() - timedelta(days=self.HISTORICAL_DAYS)).date()]
        data_types = ["latest", "historical"]
        for date, data_type in zip(dates, data_types):
            query_set = TicketCompleteness.latest_ticket_data(organization=organization, at_date=date)
            if project_key:
                query_set = query_set.filter(project__key=project_key)

            ticket_count = query_set.filter(stage__in=["Ready for Work", "Underway"]).count()
            low_score_underway_count = query_set.filter(
                stage="Underway",
                quality_category="Initial",
            ).count()
            avg_completeness_score = round(
                query_set.aggregate(Avg("completeness_score"))["completeness_score__avg"] or 0, 1
            )

            if not avg_completeness_score and data_type == "historical":
                # hide historical trends if no data is available
                response_data[data_type] = None
            else:
                response_data[data_type] = {
                    "active_tickets_count": ticket_count,
                    "low_score_underway_count": low_score_underway_count,
                    "avg_completeness_score": avg_completeness_score,
                }

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


class TicketCompletenessTrendChartView(LoginRequiredMixin, APIView):
    def get(self, request, *args, **kwargs):
        organization = request.current_organization
        project_key = request.GET.get("project_key")

        from_date = datetime.strptime(request.GET.get("from_date"), DATE_FORMAT).date()
        to_date = datetime.strptime(request.GET.get("to_date"), DATE_FORMAT).date()

        date_points = self.get_dates_to_query(from_date, to_date)
        results = self.get_trend_data(organization, project_key, date_points)

        if project_key:
            organizational_benchmark = TicketCompleteness.latest_ticket_data(organization=organization).aggregate(
                Avg("completeness_score")
            )["completeness_score__avg"]
        else:
            organizational_benchmark = None
        return Response({"results": results, "organizational_benchmark": organizational_benchmark})

    def get_trend_data(self, organization, project_key, date_points):
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self.get_specific_date_data, date, organization, project_key) for date in date_points
            ]
            results = [f.result() for f in futures]
        return sorted(results, key=lambda x: x["date"])

    @staticmethod
    def get_specific_date_data(date, organization, project_key):
        queryset = TicketCompleteness.latest_ticket_data(organization=organization, at_date=date)
        if project_key:
            queryset = queryset.filter(project__key=project_key)

        ticket_count = queryset.count()
        avg_completeness_score = (
            queryset.aggregate(Avg("completeness_score"))["completeness_score__avg"] if ticket_count else None
        )

        return {
            "date": date.strftime("%Y-%m-%d"),
            "ticket_count": ticket_count,
            "avg_completeness_score": avg_completeness_score,
        }

    def get_dates_to_query(self, from_date, to_date):
        if to_date - from_date <= timedelta(days=14):
            # daily intervals
            return [from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)]
        if to_date - from_date <= timedelta(days=90):
            # weekly intervals
            return [from_date + timedelta(weeks=i) for i in range((to_date - from_date).days // 7 + 1)]
        return [from_date + timedelta(days=30 * i) for i in range((to_date - from_date).days // 30 + 1)]


class MessageFilterView(LoginRequiredMixin, APIView):
    def get(self, request, *args, **kwargs):
        current_organization = request.current_organization
        options = self.get_options(current_organization)
        try:
            daily_message_filter = MessageFilter.objects.get(
                user=request.user,
                organization=current_organization,
                day_interval=DayIntervalChoices.ONE_DAY,
            )
        except MessageFilter.DoesNotExist:
            daily_message_filter = None

        daily_message_filter_serialized = MessageFilterSerializer(
            daily_message_filter, context={"current_organization": current_organization}
        ).data

        return Response(
            {
                "options": options,
                "daily_message_filter": daily_message_filter_serialized,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        current_organization = request.current_organization

        daily_message_filter, _ = MessageFilter.objects.get_or_create(
            user=request.user,
            organization=current_organization,
            day_interval=DayIntervalChoices.ONE_DAY,
        )

        daily_message_filter_serialized = MessageFilterSerializer(
            daily_message_filter,
            data=request.data,
            partial=True,
            context={"current_organization": current_organization},
        )

        options = self.get_options(current_organization)
        if daily_message_filter_serialized.is_valid():
            daily_message_filter_serialized.save()
            return Response(
                {
                    "options": options,
                    "daily_message_filter": daily_message_filter_serialized.data,
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                daily_message_filter_serialized.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

    def get_options(self, organization):
        significance_levels = [{"id": str(level[0]), "name": level[1]} for level in SignificanceLevelChoices.choices]
        repository_groups = RepositoryGroup.objects.filter(organization=organization)
        repository_groups_serialized = RepositoryGroupSimpleSerializer(repository_groups, many=True).data
        ticket_categories = [{"id": category[0], "name": category[1]} for category in TicketCategoryChoices.choices]

        options = {
            "significance_levels": significance_levels,
            "repository_groups": repository_groups_serialized,
            "ticket_categories": ticket_categories,
        }

        return options


class AnomalyInsightsView(LoginRequiredMixin, APIView):
    page_size = 50
    pagination_class = PageNumberPagination

    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        def get_list(param):
            return request.GET.get(param, "").split(",") if request.GET.get(param) else []

        anomaly_types = get_list("anomaly_types")
        significance_scores = [int(s) for s in get_list("significance_scores") if s]
        repository_names = get_list("repository_names")
        project_names = get_list("project_names")
        categories = get_list("categories")
        confidence_levels = get_list("confidence_levels")

        date_from = parse_date_param(request, "date_from")
        date_to = parse_date_param(request, "date_to")

        sort_by = request.GET.get("sort_by", "created_at")
        sort_order = request.GET.get("sort_order", "desc")
        sort_order = "" if sort_order == "asc" else "-"

        queryset = self.organization_filter(organization).select_related("project", "repository")
        first_date = queryset.order_by("created_at").first().created_at.date() if queryset.exists() else None

        filters = [
            (anomaly_types, {"anomaly_type__in": anomaly_types}),
            (significance_scores, {"significance_score__in": significance_scores}),
            (repository_names, {"repository__name__in": repository_names}),
            (project_names, {"project__name__in": project_names}),
            (date_from, {"created_at__date__gte": date_from}),
            (date_to, {"created_at__date__lte": date_to}),
            (categories, {"category__in": categories}),
            (confidence_levels, {"confidence_level__in": confidence_levels}),
        ]

        for cond, kwargs in filters:
            if cond:
                queryset = queryset.filter(**kwargs)

        if sort_by == "confidence_level":
            # confidence level is not lexicographically sortable, so we need to sort it manually
            queryset = self.apply_confidence_level_sorting(queryset, sort_order)
        else:
            queryset = queryset.order_by(f"{sort_order}{sort_by}")

        paginator = self.pagination_class()
        paginator.page_size = self.page_size

        page = paginator.paginate_queryset(queryset, request)
        anomalies = AnomalyInsightsSerializer(page, many=True)

        filter_options = self.get_filter_options(organization)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "results": anomalies.data,
            "filter_options": filter_options,
            "first_date": first_date.strftime(DATE_FORMAT) if first_date else None,
        }

        return Response(response_data)

    def apply_confidence_level_sorting(self, queryset, sort_order):
        confidence_order = Case(
            When(confidence_level="Low", then=1),
            When(confidence_level="Medium", then=2),
            When(confidence_level="High", then=3),
            default=0,
            output_field=IntegerField(),
        )
        return queryset.annotate(confidence_order=confidence_order).order_by(f"{sort_order}confidence_order")

    def organization_filter(self, organization):
        return AnomalyInsights.objects.filter(
            Q(project__organization=organization) | Q(repository__organization=organization)
        )

    def get_filter_options(self, organization):
        anomaly_types = (
            self.organization_filter(organization)
            .values_list("anomaly_type", flat=True)
            .distinct()
            .order_by("anomaly_type")
        )

        significance_scores = (
            self.organization_filter(organization)
            .values_list("significance_score", flat=True)
            .distinct()
            .order_by("significance_score")
        )

        repository_names = (
            self.organization_filter(organization)
            .exclude(repository__isnull=True)
            .values_list("repository__name", flat=True)
            .distinct()
            .order_by("repository__name")
        )

        project_names = (
            self.organization_filter(organization)
            .exclude(project__isnull=True)
            .values_list("project__name", flat=True)
            .distinct()
            .order_by("project__name")
        )

        categories = (
            self.organization_filter(organization).values_list("category", flat=True).distinct().order_by("category")
        )

        confidence_levels = (
            self.organization_filter(organization)
            .values_list("confidence_level", flat=True)
            .distinct()
            .order_by("confidence_level")
        )

        return {
            "anomaly_types": list(anomaly_types),
            "significance_scores": list(significance_scores),
            "repository_names": list(repository_names),
            "project_names": list(project_names),
            "categories": list(categories),
        }

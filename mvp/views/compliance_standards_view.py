from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Case, Prefetch, Q, Value, When
from django.views.generic import ListView

from mvp.mixins import DecodePublicIdMixin
from mvp.models import (
    ComplianceStandard,
    ComplianceStandardAIUsage,
    ComplianceStandardReference,
    ComplianceStandardRiskLevelChoices,
    ComplianceStandardRiskTypeChoices,
    ComplianceStandardSourceChoices,
    ComplianceStandardStatusChoices,
    Geography,
    Industry,
)

# used to sort status
STATUS_ORDER = {
    ComplianceStandardStatusChoices.CONTEMPLATED: 1,
    ComplianceStandardStatusChoices.PROPOSED: 2,
    ComplianceStandardStatusChoices.CLOSE_TO_IMPLEMENTATION: 3,
    ComplianceStandardStatusChoices.PARTIALLY_IN_EFFECT: 4,
    ComplianceStandardStatusChoices.FULLY_IMPLEMENTED: 5,
    ComplianceStandardStatusChoices.TO_BE_DETERMINED: 6,
}

# used to sort risk level
RISK_LEVEL_ORDER = {
    ComplianceStandardRiskLevelChoices.CRITICAL: 1,
    ComplianceStandardRiskLevelChoices.HIGH: 2,
    ComplianceStandardRiskLevelChoices.MEDIUM: 3,
    ComplianceStandardRiskLevelChoices.LOW: 4,
    ComplianceStandardRiskLevelChoices.TO_BE_DETERMINED: 5,
}


class ComplianceStandardsView(LoginRequiredMixin, PermissionRequiredMixin, DecodePublicIdMixin, ListView):
    permission_required = "mvp.can_view_compliance_standards"
    template_name = "mvp/ai_code_monitor/compliance-standards.html"
    paginate_by = 20
    queryset = ComplianceStandard.objects.prefetch_related(
        "industries",
        "components",
        "geographies",
        "ai_usage",
        Prefetch(
            "references",
            queryset=ComplianceStandardReference.objects.filter(url__isnull=False),
        ),
    ).filter(is_excluded=False)
    filter_fields = [
        "location",
        "risk_level",
        "ai_usage",
        "industry",
        "status",
        "source",
        "risk_type",
        "order",
        "search",
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_industries = None
        self._all_geographies = None

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_filters(queryset)
        queryset = self.apply_search(queryset)
        queryset = self.apply_order(queryset)

        return queryset.distinct()

    def apply_filters(self, queryset):
        current_org = self.request.current_organization
        # Apply filters
        filter_params = dict(self.get_filter_params())
        if filter_params:
            if "risk_level" in filter_params:
                queryset = queryset.filter(risk_level__in=filter_params["risk_level"])
            if "location" in filter_params and "all" not in filter_params["location"]:
                loc_ids = [self.decode_id(p_id) for p_id in filter_params["location"]]
                queryset = queryset.filter(geographies__id__in=loc_ids)
            if "ai_usage" in filter_params:
                query = Q(ai_usage__name__in=filter_params["ai_usage"])
                if "To be determined" in filter_params["ai_usage"]:
                    query = query | Q(ai_usage=None)
                queryset = queryset.filter(query)

            if (
                "industry" in filter_params
                and "all" not in filter_params["industry"]
                and Industry.LABEL_NONE not in filter_params["industry"]
            ):
                queryset = queryset.filter(industries__name__in=filter_params["industry"])
            if "status" in filter_params:
                queryset = queryset.filter(status__in=filter_params["status"])
            if "source" in filter_params:
                queryset = queryset.filter(source__in=filter_params["source"])
            if "risk_type" in filter_params:
                queryset = queryset.filter(risk_type__in=filter_params["risk_type"])

        if "location" not in filter_params and not current_org.is_all_geographies():
            queryset = queryset.filter(geographies__in=current_org.geographies.all())

        if "industry" not in filter_params and current_org.industry is not None:
            queryset = queryset.filter(industries=current_org.industry)

        return queryset

    def apply_search(self, queryset):
        filter_params = dict(self.get_filter_params())
        search_term = filter_params.get("search", [""])[0]
        if search_term:
            search_query = SearchQuery(search_term)
            search_vector = SearchVector("name", weight="A") + SearchVector(
                "remediation_mitigation", "description", weight="B"
            )
            queryset = queryset.annotate(rank=SearchRank(search_vector, search_query)).filter(rank__gte=0.01)
        return queryset

    def apply_order(self, queryset):
        filter_params = dict(self.get_filter_params())
        order = filter_params.get("order", ["last_updated"])[0]
        # Note: sorting for status and risk_level has to be this way to sort by label and not key

        order_field = "-updated_at"  # default
        if order == "relevance":
            order_field = "-rank"
        elif order == "last_updated_rev":
            order_field = "updated_at"
        elif order == "status":
            order_field = Case(*[When(status=status, then=Value(STATUS_ORDER.get(status))) for status in STATUS_ORDER])
        elif order == "status_rev":
            order_field = Case(*[When(status=status, then=-Value(STATUS_ORDER.get(status))) for status in STATUS_ORDER])
        elif order == "risk_level":
            order_field = Case(
                *[
                    When(
                        risk_level=risk_level,
                        then=Value(RISK_LEVEL_ORDER.get(risk_level)),
                    )
                    for risk_level in RISK_LEVEL_ORDER
                ]
            )
        elif order == "risk_level_rev":
            order_field = Case(
                *[
                    When(
                        risk_level=risk_level,
                        then=-Value(RISK_LEVEL_ORDER.get(risk_level)),
                    )
                    for risk_level in RISK_LEVEL_ORDER
                ]
            )
        return queryset.order_by(order_field, "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_org = self.request.current_organization

        return context | {
            "selected_filters": self.get_selected_filters(current_org),
            "query_params": self.get_filter_params().urlencode(),
            "risk_levels": ComplianceStandardRiskLevelChoices.choices,
            "geographies": self.get_all_geographies(),
            "ai_usages": [*list(ComplianceStandardAIUsage.objects.values_list("name", flat=True)), "To be determined"],
            "industries": self.get_all_industries(),
            "industry_none": Industry.LABEL_NONE,
            "statuses": ComplianceStandardStatusChoices.choices,
            "sources": ComplianceStandardSourceChoices.choices,
            "risk_types": ComplianceStandardRiskTypeChoices.choices,
        }

    def get_all_industries(self):
        if self._all_industries is None:
            self._all_industries = sorted([*list(Industry.objects.values_list("name", flat=True)), Industry.LABEL_NONE])

        return self._all_industries

    def get_all_geographies(self):
        if self._all_geographies is None:
            self._all_geographies = Geography.get_sorted_geographies()

        return self._all_geographies

    def get_filter_params(self):
        filter_params = self.request.GET.copy()
        # pop fields that are not in filter_fields
        keys = list(filter_params.keys())
        for key in keys:
            if key not in self.filter_fields:
                filter_params.pop(key, None)
        return filter_params

    def get_geography_ids_with_ancestors(self, loc_ids):
        geographies = Geography.objects.filter(id__in=loc_ids)
        ancestors_id = [geo.get_ancestors().values_list("id", flat=True) for geo in geographies]
        ancestors_id = [i for sublist in ancestors_id for i in sublist]
        return set(loc_ids + ancestors_id)

    def get_selected_filters(self, organization):
        filter_params = dict(self.get_filter_params())

        selected_filters = {
            "geographies": organization.geographies.all().values_list("id", flat=True),
            "all_geographies_selected": organization.is_all_geographies(),
            "industry": ([organization.industry.name] if organization.industry else ["all"]),
        }

        for key in self.filter_fields:
            if key in filter_params:
                selected_filters[key] = filter_params[key]

        # location is a special case
        if "location" in filter_params:
            loc_ids = [self.decode_id(p_id) for p_id in filter_params["location"]]
            selected_filters["geographies"] = Geography.objects.filter(id__in=loc_ids).values_list("id", flat=True)
            selected_filters["all_geographies_selected"] = "all" in filter_params["location"]

        return selected_filters

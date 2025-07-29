from django.contrib import admin

from compass.contextualization.forms import MessageFilterForm
from compass.contextualization.models import (
    AnomalyInsights,
    DailyMessage,
    Initiative,
    InitiativeEpic,
    MessageFilter,
    ReconcilableInitiative,
    Roadmap,
    TicketCompleteness,
)


@admin.register(Roadmap)
class RoadmapAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "start_date",
        "day_interval",
        "organization",
        "created_at",
    )
    list_filter = ["organization", "day_interval"]
    readonly_fields = ("organization", "repository_group", "created_at", "updated_at")


@admin.register(Initiative)
class InitiativeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "organization",
        "custom_name",
        "pinned",
        "roadmap",
        "created_at",
    )
    list_editable = ("custom_name", "pinned")
    list_filter = ["roadmap__organization", "roadmap"]
    search_fields = ["name", "custom_name"]
    readonly_fields = ("roadmap", "created_at", "updated_at")

    def organization(self, obj):
        return obj.roadmap.organization if obj.roadmap else None


@admin.register(InitiativeEpic)
class InitiativeEpicAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "custom_name",
        "pinned",
        "initiative",
        "parent_id",
        "created_at",
    )
    list_editable = ("custom_name", "pinned")
    list_filter = ["initiative__roadmap__organization", "initiative__roadmap"]
    search_fields = ["name", "custom_name"]
    readonly_fields = ("initiative", "created_at", "updated_at")

    def parent_id(self, obj):
        return obj.initiative.id if obj.initiative else None

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("initiative", "initiative__roadmap", "initiative__roadmap__organization")
        )


@admin.register(ReconcilableInitiative)
class ReconcilableInitiativeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "organization",
        "roadmap",
        "created_at",
    )
    list_filter = ["roadmap__organization"]
    readonly_fields = ("roadmap", "created_at", "updated_at")

    def organization(self, obj):
        return obj.roadmap.organization if obj.roadmap else None


@admin.register(DailyMessage)
class DailyMessageAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "date",
        "created_at",
    )
    list_filter = ["organization", "date"]
    readonly_fields = ("organization", "created_at", "updated_at")


@admin.register(MessageFilter)
class MessageFilterAdmin(admin.ModelAdmin):
    form = MessageFilterForm
    list_display = ("user", "organization", "day_interval")
    list_filter = ["user", "organization", "day_interval"]
    filter_horizontal = ("repository_groups",)
    readonly_fields = ("user", "organization", "created_at", "updated_at")


@admin.register(TicketCompleteness)
class TicketCompletenessAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_id",
        "name",
        "completeness_score",
        "llm_category",
        "stage",
        "date",
    )
    list_filter = ["llm_category", "stage", "date", "project__organization"]
    search_fields = ["ticket_id", "project__key"]
    readonly_fields = ("project", "created_at", "updated_at")


@admin.register(AnomalyInsights)
class AnomalyInsightsAdmin(admin.ModelAdmin):
    list_display = (
        "anomaly_id",
        "anomaly_type",
        "title",
        "significance_score",
        "confidence_level",
        "category",
        "project",
        "repository",
        "created_at",
    )
    list_filter = [
        "anomaly_type",
        "significance_score",
        "confidence_level",
        "category",
        "project__organization",
        "repository__organization",
        "created_at",
    ]
    search_fields = [
        "anomaly_id",
        "title",
        "evidence",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("project", "repository")

from datetime import datetime

from django.template.loader import render_to_string
from jira2markdown import convert
from rest_framework import serializers

from compass.contextualization.models import (
    AnomalyInsights,
    Initiative,
    InitiativeEpic,
    MessageFilter,
    ReconcilableInitiative,
    Roadmap,
    TicketCompleteness,
)
from mvp.mixins import DecodePublicIdMixin
from mvp.models import RepositoryGroup
from mvp.services import ContextualizationService


class InitiativeEpicSerializer(serializers.ModelSerializer):
    class Meta:
        model = InitiativeEpic
        fields = ["name", "description", "percentage"]


class InitiativeSerializer(serializers.ModelSerializer):
    epics = InitiativeEpicSerializer(many=True)
    delivery_estimate = serializers.SerializerMethodField()

    def get_delivery_estimate(self, obj):
        delivery_estimate = obj.delivery_estimate
        if not delivery_estimate:
            return None

        calculation_method = delivery_estimate.get("calculation_method", {})
        delivery_estimate["text_data_sources_used"] = ", ".join(calculation_method.get("data_sources_used", []))
        delivery_estimate["text_key_metrics_used"] = "\n- ".join(calculation_method.get("key_metrics_used", []))
        delivery_estimate["text_formulas_applied"] = "\n- ".join(calculation_method.get("formulas_applied", []))

        delivery_acceleration = delivery_estimate.get("delivery_acceleration", {})
        delivery_estimate["text_highest_impact_recommendations"] = "\n- ".join(
            delivery_acceleration.get("highest_impact_recommendations", [])
        )
        delivery_estimate["text_resource_considerations"] = "\n- ".join(
            delivery_acceleration.get("resource_considerations", [])
        )

        additional_data_needs = delivery_estimate.get("additional_data_needs", {})
        delivery_estimate["text_data_gaps"] = ", ".join(additional_data_needs.get("data_gaps", []))
        delivery_estimate["text_suggested_tracking_improvements"] = "\n".join(
            additional_data_needs.get("suggested_tracking_improvements", [])
        )

        text_content = render_to_string(
            template_name="delivery_estimate.txt",
            context=delivery_estimate,
        )
        return text_content

    class Meta:
        model = Initiative
        fields = [
            "name",
            "justification",
            "percentage",
            "percentage_tickets_done",
            "tickets_done",
            "tickets_total",
            "start_date",
            "estimated_end_date",
            "delivery_estimate",
            "epics",
        ]


class ReconcilableInitiativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconcilableInitiative
        fields = [
            "name",
            "initiative_type",
            "git_activity",
            "jira_activity",
        ]


class RoadmapSerializer(serializers.ModelSerializer):
    initiatives = InitiativeSerializer(many=True)
    reconcilable_initiatives = ReconcilableInitiativeSerializer(many=True)

    updated_at = serializers.SerializerMethodField()
    date_range = serializers.SerializerMethodField()
    default_time_window_days = serializers.SerializerMethodField()
    roadmap_ready = serializers.SerializerMethodField()

    class Meta:
        model = Roadmap
        fields = [
            "summary",
            "reconcilable_initiatives",
            "initiatives",
            "updated_at",
            "date_range",
            "default_time_window_days",
            "roadmap_ready",
        ]

    @staticmethod
    def date_to_timestamp(date):
        return datetime.combine(date, datetime.min.time()).timestamp()

    def get_updated_at(self, obj: Roadmap):
        return obj.updated_at.timestamp()

    def get_date_range(self, obj: Roadmap):
        return [
            self.date_to_timestamp(obj.start_date),
            self.date_to_timestamp(obj.end_date),
        ]

    def get_default_time_window_days(self, _obj: Roadmap):
        return ContextualizationService.DEFAULT_DAY_INTERVAL.value

    def get_roadmap_ready(self, obj: Roadmap):
        return obj is not None


class TicketCompletenessSerializer(serializers.ModelSerializer):
    project_key = serializers.CharField(source="project.key", read_only=True)

    class Meta:
        model = TicketCompleteness
        fields = [
            "ticket_id",
            "name",
            "project_key",
            "llm_category",
            "stage",
            "completeness_score",
            "quality_category",
        ]


class TicketCompletenessTicketSerializer(serializers.ModelSerializer):
    project_key = serializers.CharField(source="project.key", read_only=True)
    description = serializers.SerializerMethodField()

    def get_description(self, obj):
        if not obj.description:
            return None
        return convert(obj.description)

    class Meta:
        model = TicketCompleteness
        fields = [
            "ticket_id",
            "description",
            "assignee",
            "reporter",
            "completeness_score_explanation",
            "name",
            "project_key",
            "llm_category",
            "stage",
            "completeness_score",
            "quality_category",
        ]


class MessageFilterSerializer(DecodePublicIdMixin, serializers.ModelSerializer):
    significance_levels = serializers.ListField()
    day_interval = serializers.IntegerField(required=False, read_only=True)
    repository_groups = serializers.SerializerMethodField(read_only=True)
    repository_groups_public_ids = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    ticket_categories = serializers.ListField(required=False)

    class Meta:
        model = MessageFilter
        fields = [
            "day_interval",
            "significance_levels",
            "repository_groups",
            "repository_groups_public_ids",
            "ticket_categories",
        ]

    def to_internal_value(self, data):
        if "repository_groups" in data and not data.get("repository_groups_public_ids"):
            data["repository_groups_public_ids"] = data.pop("repository_groups")
        return super().to_internal_value(data)

    def get_repository_groups(self, obj):
        return [group.public_id() for group in obj.repository_groups.all()]

    def validate_repository_groups_public_ids(self, value):
        if not value:
            # Empty list means clear repository groups (clear groups means all)
            return RepositoryGroup.objects.none()
        decoded_ids = [self.decode_id(encoded_id) for encoded_id in value]
        qs = RepositoryGroup.objects.filter(
            id__in=decoded_ids,
            organization=self.context["current_organization"],
        )
        if qs.count() != len(decoded_ids):
            raise serializers.ValidationError("One or more repository groups are invalid.")
        return qs

    def update(self, instance, validated_data):
        if "significance_levels" in validated_data:
            instance.significance_levels = validated_data.pop("significance_levels")
        if "repository_groups_public_ids" in validated_data:
            instance.repository_groups.set(validated_data.pop("repository_groups_public_ids"))
        if "ticket_categories" in validated_data:
            instance.ticket_categories = validated_data.pop("ticket_categories")

        return super().update(instance, validated_data)


class AnomalyInsightsSerializer(serializers.ModelSerializer):
    repository_name = serializers.CharField(source="repository.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = AnomalyInsights
        fields = [
            "anomaly_id",
            "anomaly_type",
            "significance_score",
            "title",
            "insight",
            "repository_name",
            "project_name",
            "category",
            "confidence_level",
            "ticket_categories",
            "created_at",
        ]

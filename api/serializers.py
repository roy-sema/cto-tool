from rest_framework import serializers

from api.models import GenAIFeedback
from mvp.models import CustomUser
from mvp.utils import get_file_url


class GenAIFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenAIFeedback
        fields = (
            "id",
            "file",
            "code_line_start",
            "code_line_end",
            "vote",
            "comment",
            "status",
            "file_path",
        )

    def validate_file_field(self, value):
        if value.size == 0:
            raise serializers.ValidationError("File is empty")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data["content_hash"] = self.context["request"].content_hash
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.vote = validated_data.get("vote", instance.vote)
        instance.comment = validated_data.get("comment", instance.comment)
        instance.save()
        return instance

    def to_internal_value(self, data):
        if "status" in data and isinstance(data["status"], str):
            data._mutable = True
            data["status"] = data["status"].lower()
            data._mutable = False
        internal_value = super().to_internal_value(data)
        internal_value["status"] = data["status"].lower()
        return internal_value


class CurrentUserSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    organizations = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "initials",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "organization",
            "organizations",
            "profile_image",
            "profile_image_thumbnail",
            "hide_environment_banner",
        ]
        read_only_fields = ["is_staff", "hide_environment_banner"]

    def get_organization(self, obj):
        current_org = self.context["request"].current_organization
        return {
            "id": current_org.public_id(),
            "onboarding_completed": current_org.onboarding_completed,
        }

    def get_organizations(self, obj):
        return self.context["request"].user_organizations_public_map

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["profile_image"] = get_file_url(instance.profile_image)
        data["profile_image_thumbnail"] = get_file_url(instance.profile_image_thumbnail)
        return data

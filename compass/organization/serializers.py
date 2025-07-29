from rest_framework import serializers

from mvp.models import AuthorGroup, CustomUser, RepositoryGroup


class OrganizationAuthorGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorGroup
        fields = [
            "public_id",
            "name",
        ]


class OrganizationRepositoryGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepositoryGroup
        fields = [
            "public_id",
            "name",
        ]


class OrganizationUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "public_id",
            "email",
        ]

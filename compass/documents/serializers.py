from rest_framework import serializers

from compass.documents.models import Document
from mvp.utils import get_file_url


class DocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "public_id",
            "name",
            "url",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["url"] = get_file_url(instance.url)
        return data


class CreateDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "name",
            "organization",
            "file",
            "uploaded_by",
        ]

    def create(self, validated_data):
        return Document.objects.create(**validated_data)

from rest_framework import serializers

from compass.projects.models import ChatHistory


class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = [
            "result",
            "status",
        ]

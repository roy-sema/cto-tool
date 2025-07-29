from rest_framework import serializers


class InsightsNotificationsSerializer(serializers.Serializer):
    anomaly_insights = serializers.BooleanField()
    summary_insights = serializers.BooleanField()

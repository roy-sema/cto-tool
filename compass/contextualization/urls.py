from django.urls import path

from compass.contextualization.views import (
    AnomalyInsightsView,
    DailyMessageView,
    MessageFilterView,
    TicketCompletenessStatisticsView,
    TicketCompletenessTicketView,
    TicketCompletenessTrendChartView,
    TicketCompletenessView,
)

urlpatterns = [
    path("daily-message", DailyMessageView.as_view(), name="compass_api_daily_message"),
    path(
        "message-filter",
        MessageFilterView.as_view(),
        name="compass_api_daily_message_filter",
    ),
    path(
        "ticket-completeness",
        TicketCompletenessView.as_view(),
        name="compass_api_ticket_completeness",
    ),
    path(
        "ticket-completeness/ticket",
        TicketCompletenessTicketView.as_view(),
        name="compass_api_ticket_completeness_ticket",
    ),
    path(
        "ticket-completeness/statistics",
        TicketCompletenessStatisticsView.as_view(),
        name="compass_api_ticket_completeness_statistics",
    ),
    path(
        "ticket-completeness/trend-chart",
        TicketCompletenessTrendChartView.as_view(),
        name="compass_api_ticket_completeness_trend_chart",
    ),
    path(
        "anomaly-insights",
        AnomalyInsightsView.as_view(),
        name="compass_api_anomaly_insights",
    ),
]

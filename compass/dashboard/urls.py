from django.urls import path

from compass.dashboard.views import (
    DashboardView,
    GenerateInsightsView,
    SIPDashboardView,
    SIPProductRoadmapRadarView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="compass_api_dashboard"),
    path("insights/", GenerateInsightsView.as_view(), name="compass_api_dashboard"),
    path("sip/", SIPDashboardView.as_view(), name="compass_api_sip_dashboard"),
    path(
        "sip/product-roadmap-radar/",
        SIPProductRoadmapRadarView.as_view(),
        name="compass_api_sip_product_roadmap_radar",
    ),
]

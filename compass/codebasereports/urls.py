from django.urls import path

from compass.codebasereports.views import (
    ComplianceDetailView,
    ExecutiveSummaryView,
    ProductDetailView,
)

urlpatterns = [
    path(
        "compliance-detail/",
        ComplianceDetailView.as_view(),
        name="compass_api_compliance_detail",
    ),
    path(
        "executive-summary/",
        ExecutiveSummaryView.as_view(),
        name="compass_api_executive_summary",
    ),
    path(
        "product-detail/",
        ProductDetailView.as_view(),
        name="compass_api_product_detail",
    ),
]

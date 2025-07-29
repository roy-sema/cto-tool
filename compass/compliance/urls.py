from django.urls import path

from compass.compliance.views import ComplianceView

urlpatterns = [path("", ComplianceView.as_view(), name="compass_api_compliance")]

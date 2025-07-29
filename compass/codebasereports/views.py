from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from compass.codebasereports.widgets import (
    CaveatsWidget,
    CodacyWidget,
    ConnectionsWidget,
    IRadarWidget,
    ProcessWidget,
    SemaScoreWidget,
    SnykWidget,
    TeamWidget,
)
from mvp.services import ConnectedIntegrationsService


def get_request_dates(request):
    until = parse_date_param(request, "until") or datetime.utcnow().date()
    since = parse_date_param(request, "since") or until - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS)
    return since, until


class ExecutiveSummaryView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_insights"

    def get(self, request):
        current_org = request.current_organization
        since, until = get_request_dates(request)
        integrations = ConnectedIntegrationsService().get_connected_integration_statuses(
            current_org, ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS
        )

        return Response(
            {
                **CaveatsWidget(current_org).get_widgets(),
                **ConnectionsWidget(current_org).get_widgets(),
                **IRadarWidget(current_org).get_widgets(since, until),
                **ProcessWidget(current_org).get_widgets(since, until),
                **SemaScoreWidget(current_org).get_widgets(since, until),
                **SnykWidget(current_org).get_widgets(since, until),
                **TeamWidget(current_org).get_widgets(since, until),
                "default_time_window_days": settings.DEFAULT_TIME_WINDOW_DAYS,
                "org_first_date": current_org.get_first_commit_date(),
                "since": since,
                "until": until,
                "integrations": integrations,
            }
        )


class ProductDetailView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_insights"

    def get(self, request):
        current_org = request.current_organization
        since, until = get_request_dates(request)
        integrations = ConnectedIntegrationsService().get_connected_integration_statuses(
            current_org, ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS
        )

        return Response(
            {
                **CodacyWidget(current_org).get_widgets(since, until),
                **ConnectionsWidget(current_org).get_widgets(ConnectionsWidget.MODULES_PRODUCT),
                **ProcessWidget(current_org).get_widgets(since, until),
                **TeamWidget(current_org).get_widgets(since, until),
                "default_time_window_days": settings.DEFAULT_TIME_WINDOW_DAYS,
                "org_first_date": current_org.get_first_commit_date(),
                "since": since,
                "until": until,
                "integrations": integrations,
            }
        )


class ComplianceDetailView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_insights"

    def get(self, request):
        current_org = request.current_organization
        since, until = get_request_dates(request)
        data = {
            **ConnectionsWidget(current_org).get_widgets(ConnectionsWidget.MODULES_COMPLIANCE),
            **IRadarWidget(current_org).get_widgets(since, until),
            **SnykWidget(current_org).get_widgets(since, until),
        }
        integrations = ConnectedIntegrationsService().get_connected_integration_statuses(
            current_org, ConnectedIntegrationsService.GIT_INTEGRATION_MAP_KEYS
        )

        return Response(
            {
                **data,
                # TODO: uncomment if we want to get it back.
                # Frontend needs to be implemented in Vue => check git history for scatter chart
                # **CombinedWidget(current_org).get_widgets(data),
                "default_time_window_days": settings.DEFAULT_TIME_WINDOW_DAYS,
                "org_first_date": current_org.get_first_commit_date(),
                "since": since,
                "until": until,
                "integrations": integrations,
            }
        )

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from api.utils import parse_date_param
from compass.codebasereports.widgets import ProcessWidget


class OrganizationMetricsView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_ai_code_monitor"

    def get(self, request, *args, **kwargs):
        current_org = request.current_organization

        until = parse_date_param(request, "until") or datetime.utcnow().date()
        since = parse_date_param(request, "since") or until - timedelta(days=settings.DEFAULT_TIME_WINDOW_DAYS)
        chart_process_commits, chart_process_files = ProcessWidget(current_org).get_charts(since, until)

        return Response(
            {
                "chart_process_files": chart_process_files,
                "chart_process_commits": chart_process_commits,
            }
        )

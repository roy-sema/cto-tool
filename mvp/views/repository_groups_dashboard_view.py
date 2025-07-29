from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from mvp.mixins import DecodePublicIdMixin


class RepositoryGroupsDashboardView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_pull_request_scans"

    def get(self, request):
        current_org = request.current_organization

        has_repositories = current_org.repository_set.exists()
        first_commit_date = current_org.get_first_commit_date()
        updated_at = current_org.get_last_commit_timestamp()

        return render(
            request,
            "mvp/ai_code_monitor/repository-groups-dashboard.html",
            {
                "has_repositories": has_repositories,
                "org_first_date": first_commit_date,
                "default_time_window_days": settings.DEFAULT_TIME_WINDOW_DAYS,
                "updated_at": updated_at,
            },
        )

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from mvp.mixins import DecodePublicIdMixin
from mvp.models import Author


class DeveloperGroupsDashboardView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_ai_code_monitor"

    def get(self, request):
        current_org = request.current_organization
        developers_count = Author.objects.filter(organization=current_org, linked_author__isnull=True).count()
        org_first_date = current_org.get_first_commit_date()
        updated_at = current_org.get_last_commit_timestamp()

        return render(
            request,
            "mvp/ai_code_monitor/developer-groups-dashboard.html",
            {
                "developers_count": developers_count,
                "org_first_date": org_first_date,
                "default_time_window_days": settings.DEFAULT_TIME_WINDOW_DAYS,
                "updated_at": updated_at,
            },
        )

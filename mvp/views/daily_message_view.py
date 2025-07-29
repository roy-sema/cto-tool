from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from mvp.mixins import DecodePublicIdMixin


class DailyMessageView(LoginRequiredMixin, PermissionRequiredMixin, DecodePublicIdMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request):
        return render(request, "mvp/settings/daily-message.html")

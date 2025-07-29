from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View


class HomeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_view_compass_dashboard"

    def get(self, request):
        return render(request, "compass/index.html")

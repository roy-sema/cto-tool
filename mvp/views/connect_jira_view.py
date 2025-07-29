from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View


class ConnectJiraView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return render(request, "mvp/settings/jira-connection.html")

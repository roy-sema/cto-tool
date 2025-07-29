import posthog
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from mvp.forms import ConnectMSTeamsForm
from mvp.models import MessageIntegration, MessageIntegrationServiceChoices


class ConnectMSTeamsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return self.render_form(request, ConnectMSTeamsForm(instance=self.get_or_create_message_integration(request)))

    def post(self, request):
        form = ConnectMSTeamsForm(request.POST, instance=self.get_or_create_message_integration(request))

        if form.is_valid():
            form.instance.connected_by = request.user
            form.instance.connected_at = timezone.now()
            form.instance.enabled = True
            form.save()

            posthog.capture(request.user.email, event="connect_ms_teams")
            messages.success(request, "MS Teams connected!")
            return redirect(reverse_lazy("connect_ms_teams"))

        return self.render_form(request, form)

    def render_form(self, request, form):
        return render(request, "mvp/settings/connect-ms-teams.html", {"form": form})

    def get_or_create_message_integration(self, request) -> MessageIntegration:
        integration, _created = MessageIntegration.objects.get_or_create(
            organization=request.current_organization,
            service=MessageIntegrationServiceChoices.MS_TEAMS,
            defaults={"enabled": False},
        )
        return integration

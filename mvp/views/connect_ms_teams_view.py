import logging

import posthog
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.integrations.ms_teams import MsTeamsIntegration
from mvp.forms import ConnectMSTeamsForm
from mvp.models import MessageIntegration, MessageIntegrationServiceChoices
from mvp.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ConnectMSTeamsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return self.render_form(request, ConnectMSTeamsForm(instance=self.get_or_create_message_integration(request)))

    def post(self, request):
        action = request.POST.get("action")
        if action == "send_message":
            return self.send_test_message(request)
        return self.handle_save(request)

    def send_test_message(self, request):
        integration = self.get_or_create_message_integration(request)
        try:
            NotificationService.send_teams_notification(
                integration,
                "This is a test message from Sema. Your Microsoft Teams connection is working.",
            )
            messages.success(request, "Test message is sent!")
        except Exception as e:
            logger.exception("Failed to send test message", exc_info=e)
            messages.error(request, "Failed to send test message. Verify connection settings or contact support.")
        return redirect(reverse_lazy("connect_ms_teams"))

    def handle_save(self, request):
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

    def render_form(self, request, form, extra=None):
        integration = form.instance
        context = {
            "form": form,
            "is_connected": integration and MsTeamsIntegration.is_connection_connected(integration),
        }
        if extra:
            context.update(extra)
        return render(request, "mvp/settings/connect-ms-teams.html", context)

    def get_or_create_message_integration(self, request) -> MessageIntegration:
        integration, _created = MessageIntegration.objects.get_or_create(
            organization=request.current_organization,
            service=MessageIntegrationServiceChoices.MS_TEAMS,
            defaults={"enabled": False},
        )
        return integration

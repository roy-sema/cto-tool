import posthog
import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.apis import IRadarRestApi
from compass.integrations.integrations import IRadarIntegration
from mvp.forms import ConnectIRadarForm
from mvp.models import DataProviderConnection
from mvp.utils import start_new_thread, traceback_on_debug


class ConnectIRadarView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return self.render_form(request, ConnectIRadarForm(instance=self.get_or_create_connection(request)))

    def post(self, request):
        form = ConnectIRadarForm(request.POST, instance=self.get_or_create_connection(request))

        if form.is_valid():
            try:
                api = IRadarRestApi()
                api.set_auth_token(form.cleaned_data["username"], form.cleaned_data["password"])
                connection = form.save()
                connection.connected_by = request.user
                connection.connected_at = timezone.now()
                connection.save()
                self.fetch_data_background(connection)

                posthog.capture(request.user.email, event="connect_iradar")

                messages.success(request, "iRADAR connected!")
                return redirect(reverse_lazy("connect_iradar"))
            except requests.exceptions.HTTPError:
                traceback_on_debug()
                messages.error(request, "Connection failed. Please try again")

        return self.render_form(request, form)

    def render_form(self, request, form):
        return render(request, "mvp/settings/connect-iradar.html", {"form": form})

    def get_or_create_connection(self, request):
        connection, created = DataProviderConnection.objects.get_or_create(
            provider=IRadarIntegration().provider,
            organization=request.current_organization,
        )
        return connection

    @start_new_thread
    def fetch_data_background(self, connection):
        IRadarIntegration().fetch_data(connection)

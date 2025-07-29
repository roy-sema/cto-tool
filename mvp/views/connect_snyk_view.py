import posthog
import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.apis import SnykRestApi
from compass.integrations.integrations import SnykIntegration
from mvp.forms import ConnectSnykForm
from mvp.models import DataProviderConnection
from mvp.utils import start_new_thread, traceback_on_debug


class ConnectSnykView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return self.render_form(request, ConnectSnykForm(instance=self.get_or_create_connection(request)))

    def post(self, request):
        form = ConnectSnykForm(request.POST, instance=self.get_or_create_connection(request))

        if form.is_valid():
            try:
                api = SnykRestApi(form.cleaned_data["api_token"])
                api.get_organization(form.cleaned_data["org_id"])
                connection = form.save()
                connection.connected_by = request.user
                connection.connected_at = timezone.now()
                connection.save()
                self.fetch_data_background(connection)

                posthog.capture(request.user.email, event="connect_snyk")

                messages.success(request, "Snyk connected!")
                return redirect(reverse_lazy("connect_snyk"))
            except requests.exceptions.HTTPError:
                traceback_on_debug()
                messages.error(request, "Connection failed. Please try again")

        return self.render_form(request, form)

    def render_form(self, request, form):
        return render(request, "mvp/settings/connect-snyk.html", {"form": form})

    def get_or_create_connection(self, request):
        connection, created = DataProviderConnection.objects.get_or_create(
            provider=SnykIntegration().provider,
            organization=request.current_organization,
        )
        return connection

    @start_new_thread
    def fetch_data_background(self, connection):
        SnykIntegration().fetch_data(connection)

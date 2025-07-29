import posthog
import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.apis import CodacyApi
from compass.integrations.integrations import CodacyIntegration
from mvp.forms import ConnectCodacyForm
from mvp.models import DataProviderConnection
from mvp.utils import start_new_thread, traceback_on_debug


class ConnectCodacyView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return self.render_form(request, ConnectCodacyForm(instance=self.get_or_create_connection(request)))

    def post(self, request):
        form = ConnectCodacyForm(request.POST, instance=self.get_or_create_connection(request))

        if form.is_valid():
            try:
                api = CodacyApi(form.cleaned_data["api_token"])
                api.list_user_organizations()
                connection = form.save()
                connection.connected_by = request.user
                connection.connected_at = timezone.now()
                connection.save()
                self.fetch_data_background(connection)

                posthog.capture(request.user.email, event="connect_codacy")

                messages.success(request, "Codacy connected!")
                return redirect(reverse_lazy("connect_codacy"))
            except requests.exceptions.HTTPError:
                traceback_on_debug()
                messages.error(request, "Connection failed. Please try again")

        return self.render_form(request, form)

    def render_form(self, request, form):
        return render(request, "mvp/settings/connect-codacy.html", {"form": form})

    def get_or_create_connection(self, request):
        connection, created = DataProviderConnection.objects.get_or_create(
            provider=CodacyIntegration().provider,
            organization=request.current_organization,
        )
        return connection

    @start_new_thread
    def fetch_data_background(self, connection):
        CodacyIntegration().fetch_data(connection)

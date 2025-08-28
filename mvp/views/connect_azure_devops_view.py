import posthog
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.apis import AzureDevOpsApi, AzureDevOpsApiConfig
from compass.integrations.integrations import AzureDevOpsIntegration
from mvp.forms import ConnectAzureDevOpsForm
from mvp.models import DataProviderConnection
from mvp.services import ContextualizationService
from mvp.tasks import DownloadRepositoriesTask, ImportContextualizationDataTask
from mvp.utils import start_new_thread, traceback_on_debug


class ConnectAzureDevOpsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        return self.render_form(
            request,
            ConnectAzureDevOpsForm(instance=self.get_or_create_connection(request)),
        )

    def post(self, request):
        form = ConnectAzureDevOpsForm(request.POST, instance=self.get_or_create_connection(request))
        organization = request.current_organization

        if form.is_valid():
            try:
                api = AzureDevOpsApi(
                    AzureDevOpsApiConfig(
                        base_url=form.cleaned_data["base_url"],
                        auth_token=form.cleaned_data["personal_access_token"],
                    )
                )
                api.get_connection()
                connection = form.save()
                connection.connected_by = request.user
                connection.connected_at = timezone.now()
                connection.save()
                self.fetch_data_background(connection)

                posthog.capture(request.user.email, event="connect_azure_devops")

                if not organization.onboarding_completed:
                    return redirect("/onboarding/connect-vcs")

                messages.success(request, "AzureDevOps connected!")
                return redirect(reverse_lazy("connect_azure_devops"))
            except Exception:
                traceback_on_debug()
                messages.error(request, "Connection failed. Please try again")

        return self.render_form(request, form)

    def render_form(self, request, form):
        return render(
            request,
            "mvp/settings/connect-azure-devops.html",
            {
                "form": form,
                "azure_devops_webhook_url": f"{settings.SITE_DOMAIN}/api/webhook-azure-devops/",
            },
        )

    def get_or_create_connection(self, request):
        connection, _ = DataProviderConnection.objects.get_or_create(
            provider=AzureDevOpsIntegration().provider,
            organization=request.current_organization,
            defaults={"connected_by": request.user, "connected_at": timezone.now()},
        )
        return connection

    @start_new_thread
    def fetch_data_background(self, connection: DataProviderConnection):
        org = connection.organization
        service = ContextualizationService()
        pipelines = {
            service.PIPELINE_A,
            service.PIPELINE_BC,
            service.PIPELINE_ANOMALY_INSIGHTS,
        }

        DownloadRepositoriesTask().run(organization_id=org.id)
        results = service.process_organization(org, pipelines=pipelines)
        ImportContextualizationDataTask(organization=org, pipeline_results=results).run()
        AzureDevOpsIntegration().fetch_data(connection)

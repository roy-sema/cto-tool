import posthog
import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.apis import GitHubApi, GitHubApiConfig
from compass.integrations.integrations import GitHubIntegration
from mvp.models import DataProviderConnection
from mvp.services import ContextualizationService
from mvp.tasks import DownloadRepositoriesTask, ImportContextualizationDataTask
from mvp.utils import start_new_thread, traceback_on_debug


class ConnectGitHubView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        installation_id = request.GET.get("installation_id")
        organization = request.current_organization
        # NOTE: state is not used anymore, but we may need it in the future
        # state = request.GET.get("state")

        try:
            # check installation is successful
            GitHubApi(GitHubApiConfig(installation_id))
            connection = self.update_or_create_connection(organization, installation_id, request.user)

            # always fetch data, as GitHub installation may be re-used in different orgs
            self.fetch_data_background(connection)

            if not organization.first_analysis_done:
                organization.connection_issued_by = request.user
                organization.save()

            posthog.capture(request.user.email, event="connect_github")

            if organization.onboarding_completed:
                messages.success(request, "GitHub connected!")
        except requests.exceptions.HTTPError:
            traceback_on_debug()
            if organization.onboarding_completed:
                messages.error(request, "Connection failed. Please try again")

        destination = (
            "/onboarding/connect-vcs" if not organization.onboarding_completed else reverse_lazy("connections")
        )
        return redirect(destination)

    def update_or_create_connection(self, organization, installation_id, user):
        connection, _ = DataProviderConnection.objects.get_or_create(
            provider=GitHubIntegration().provider,
            organization=organization,
            defaults={"data": {"installation_ids": []}},
        )

        ids = set(connection.data["installation_ids"])
        ids.add(installation_id)
        connection.data["installation_ids"] = list(ids)
        connection.connected_by = user
        connection.connected_at = timezone.now()
        connection.save()

        return connection

    @start_new_thread
    def fetch_data_background(self, connection):
        org = connection.organization
        service = ContextualizationService()
        pipelines = {
            service.PIPELINE_A,
            service.PIPELINE_BC,
            service.PIPELINE_ANOMALY_INSIGHTS,
        }

        DownloadRepositoriesTask().run(organization_id=org.id)
        service.process_organization(org, pipelines=pipelines)
        ImportContextualizationDataTask().run(org)
        GitHubIntegration().fetch_data(connection)

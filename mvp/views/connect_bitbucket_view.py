import uuid

import posthog
import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from compass.integrations.apis import BitBucketApi, BitBucketApiConfig
from compass.integrations.integrations import BitBucketIntegration
from mvp.models import DataProviderConnection
from mvp.services import ContextualizationService
from mvp.tasks import DownloadRepositoriesTask, ImportContextualizationDataTask
from mvp.utils import start_new_thread, traceback_on_debug


class ConnectBitBucketView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    def get(self, request):
        code = request.GET.get("code")
        organization = request.current_organization

        try:
            access_token, refresh_token = BitBucketApi.get_oauth_access_token_by_code(code)
            config = BitBucketApiConfig(
                workspace="",  # Placeholder - getting workspace from API.
                access_token=access_token,
                refresh_token=refresh_token,
            )
            api = BitBucketApi(config)
            # TODO - getting only the first workspace for now.
            # Need to implement a way to select multiple workspaces
            # and update logic to handle multiple workspaces.
            workspace = api.list_user_workspaces()[0]["slug"]
            connection = self.get_or_create_connection(organization)
            connection.data = {
                "workspace": workspace,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "webhook_secret": uuid.uuid4().hex,
            }
            connection.connected_by = request.user
            connection.connected_at = timezone.now()
            connection.save()
            self.fetch_data_background(connection)
            self.install_webhooks(connection)

            posthog.capture(request.user.email, event="connect_bitbucket")
            if organization.onboarding_completed:
                messages.success(request, "BitBucket connected!")
        except requests.exceptions.HTTPError:
            traceback_on_debug()
            if organization.onboarding_completed:
                messages.error(request, "Connection failed. Please try again")

        destination = (
            "/onboarding/connect-vcs" if not organization.onboarding_completed else reverse_lazy("connections")
        )
        return redirect(destination)

    def get_or_create_connection(self, organization):
        connection, created = DataProviderConnection.objects.get_or_create(
            provider=BitBucketIntegration().provider,
            organization=organization,
        )
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
        results = service.process_organization(org, pipelines=pipelines)
        ImportContextualizationDataTask(organization=org, pipeline_results=results).run()
        BitBucketIntegration().fetch_data(connection)

    @start_new_thread
    def install_webhooks(self, connection):
        workspace = connection.data["workspace"]
        config = BitBucketApiConfig(
            workspace=workspace,
            access_token=connection.data["access_token"],
            refresh_token=connection.data["refresh_token"],
        )
        integration = BitBucketIntegration()
        integration.init_api(config, connection)

        # Deleting existing so new webhooks have the correct secret.
        integration.api.delete_webhooks_for_workspace(workspace)

        integration.api.install_webhooks_for_workspace(
            workspace,
            connection.data["webhook_secret"],
        )

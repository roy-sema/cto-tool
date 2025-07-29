from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from compass.integrations.apis import BitBucketApi, GitHubApi
from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    CodacyIntegration,
    GitHubIntegration,
    IRadarIntegration,
    JiraIntegration,
    SnykIntegration,
)
from mvp.models import DataProviderConnection
from mvp.services import ConnectedIntegrationsService


class ConnectionsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_connections"

    INTEGRATIONS = {
        ConnectedIntegrationsService.BITBUCKET: {
            "name": "BitBucket",
            "integration": BitBucketIntegration,
            "url": BitBucketApi.get_installation_url(
                settings.BITBUCKET_OAUTH_CONSUMER_KEY,
            ),
            "manual": True,
        },
        ConnectedIntegrationsService.CODACY: {
            "name": "Codacy",
            "integration": CodacyIntegration,
            "view": "connect_codacy",
            "manual": True,
        },
        ConnectedIntegrationsService.GITHUB: {
            "name": "GitHub",
            "integration": GitHubIntegration,
            "url": GitHubApi.get_installation_url(settings.GITHUB_APP_NAME),
            "manual": False,
        },
        ConnectedIntegrationsService.AZURE_DEVOPS: {
            "name": "Azure DevOps",
            "integration": AzureDevOpsIntegration,
            "view": "connect_azure_devops",
            "manual": True,
        },
        ConnectedIntegrationsService.JIRA: {
            "name": "Jira",
            "integration": JiraIntegration,
            "view": "connect_jira",
            "manual": False,
        },
        ConnectedIntegrationsService.IRADAR: {
            "name": "IRadar",
            "integration": IRadarIntegration,
            "view": "connect_iradar",
            "manual": True,
        },
        ConnectedIntegrationsService.SNYK: {
            "name": "Snyk",
            "integration": SnykIntegration,
            "view": "connect_snyk",
            "manual": True,
        },
    }

    COMING_SOON_PROVIDERS = [
        {"name": "Veracode"},
        {"name": "GitLab"},
    ]

    def get(self, request):
        current_org = request.current_organization

        providers = self.get_providers(current_org)

        is_github_connected = providers.get(ConnectedIntegrationsService.GITHUB, {}).get("connected")

        return render(
            request,
            "mvp/settings/connections.html",
            {
                "providers": providers.values(),
                "comming_soon": self.COMING_SOON_PROVIDERS,
                "is_github_connected": is_github_connected,
            },
        )

    def get_providers(self, organization):
        connections = DataProviderConnection.objects.filter(
            organization=organization, data__isnull=False
        ).prefetch_related("provider")

        connection_map = {connection.provider.name: connection for connection in connections}

        integrations = {}
        for integration_key, integration in self.INTEGRATIONS.items():
            connection = connection_map.get(integration["integration"]().provider.name)

            integrations[integration_key] = {
                **integration,
                "connected": connection and connection.is_connected(),
            }

        return integrations

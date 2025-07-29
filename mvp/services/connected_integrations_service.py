from compass.integrations.integrations import (
    AzureDevOpsIntegration,
    BitBucketIntegration,
    GitHubIntegration,
    IntegrationFactory,
    JiraIntegration,
)
from mvp.models import DataProviderConnection, Organization


class ConnectedIntegrationsService:
    # Code Repositories
    AZURE_DEVOPS = "azuredevops"
    BITBUCKET = "bitbucket"
    GITHUB = "github"
    # DevOps, Security & Quality
    AWS = "aws"
    JENKINS = "jenkins"
    CODACY = "codacy"
    IRADAR = "iradar"
    SNYK = "snyk"
    # Project Management & Business Tools
    JIRA = "jira"
    QUICKBOOKS = "quickbooks"
    WORKPLACE = "workplace"

    # TODO: Implement methods for other integrations
    INTEGRATION_MAP = {
        AWS: None,
        AZURE_DEVOPS: AzureDevOpsIntegration,
        BITBUCKET: BitBucketIntegration,
        CODACY: None,
        GITHUB: GitHubIntegration,
        IRADAR: None,
        JENKINS: None,
        JIRA: JiraIntegration,
        QUICKBOOKS: None,
        SNYK: None,
        WORKPLACE: None,
    }

    GIT_INTEGRATION_MAP_KEYS = [
        GITHUB,
        AZURE_DEVOPS,
        BITBUCKET,
    ]

    DISPLAY_NAME_MAP = {
        AZURE_DEVOPS: "Azure DevOps",
        BITBUCKET: "BitBucket",
        GITHUB: "GitHub",
        AWS: "AWS",
        JENKINS: "Jenkins",
        CODACY: "Codacy",
        IRADAR: "iRadar",
        SNYK: "Snyk",
        JIRA: "Jira",
        QUICKBOOKS: "QuickBooks",
        WORKPLACE: "Workplace",
    }

    @classmethod
    def get_connected_integrations(
        cls,
        organization: Organization,
        integration_map_keys: list | None = None,
    ) -> dict:
        if integration_map_keys:
            integration_map = {key: cls.INTEGRATION_MAP[key] for key in integration_map_keys}
        else:
            integration_map = cls.INTEGRATION_MAP

        return {
            key: (cls.is_integration_connected(organization, integration()) if integration else None)
            for key, integration in integration_map.items()
        }

    @classmethod
    def get_connected_integration_statuses(
        cls,
        organization: Organization,
        integration_map_keys: list | None = None,
    ) -> dict:
        connected_integrations = cls.get_connected_integrations(
            organization,
            integration_map_keys,
        )
        return {
            key: {"status": value, "display_name": cls.DISPLAY_NAME_MAP[key]}
            for key, value in connected_integrations.items()
            if value is not None
        }

    @classmethod
    def is_git_connected(cls, organization: Organization) -> bool:
        for key in cls.GIT_INTEGRATION_MAP_KEYS:
            if cls.is_integration_connected(organization, cls.INTEGRATION_MAP[key]()):
                return True
        return False

    @classmethod
    def is_azure_devops_connected(cls, organization: Organization) -> bool:
        return cls.is_integration_connected(organization, cls.INTEGRATION_MAP[cls.AZURE_DEVOPS]())

    @classmethod
    def is_bitbucket_connected(cls, organization: Organization) -> bool:
        return cls.is_integration_connected(organization, cls.INTEGRATION_MAP[cls.BITBUCKET]())

    @classmethod
    def is_github_connected(cls, organization: Organization) -> bool:
        return cls.is_integration_connected(organization, cls.INTEGRATION_MAP[cls.GITHUB]())

    @classmethod
    def is_jira_connected(cls, organization: Organization) -> bool:
        return cls.is_integration_connected(organization, cls.INTEGRATION_MAP[cls.JIRA]())

    @classmethod
    def is_integration_connected(cls, organization: Organization, integration) -> bool | None:
        connection = DataProviderConnection.objects.filter(
            organization=organization,
            data__isnull=False,
            provider=integration.provider,
        ).first()

        if not connection:
            return

        return bool(integration.is_connection_connected(connection))

    @classmethod
    def is_connection_connected(cls, connection: DataProviderConnection) -> bool:
        integration = IntegrationFactory().get_integration(connection.provider)
        if not integration:
            return False

        return cls.is_integration_connected(connection.organization, integration)

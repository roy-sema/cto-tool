import logging

from compass.integrations.apis import JiraApi, JiraApiConfig
from compass.integrations.apis.jira_api import JiraApiException
from compass.integrations.integrations import BaseIntegration
from mvp.models import (
    DataProviderConnection,
    DataProviderProject,
    JiraProject,
    ModuleChoices,
    Organization,
)

logger = logging.getLogger(__name__)


class JiraIntegration(BaseIntegration):
    DISCONNECTED_DATA_FIELD = "data_disconnected"

    def __init__(self):
        super().__init__()
        self.api = None

    def init_api(self, config: JiraApiConfig, connection: DataProviderConnection):
        self.api = JiraApi(config)
        access_token, refresh_token = self.api.refresh_tokens()
        self.update_connection_tokens(connection, access_token, refresh_token)

    @staticmethod
    def update_connection_tokens(
        connection: DataProviderConnection,
        access_token: str,
        refresh_token: str,
    ):
        connection.data["access_token"] = access_token
        connection.data["refresh_token"] = refresh_token
        connection.save()

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return bool(connection.data and connection.data.get("access_token") and connection.data.get("refresh_token"))

    @classmethod
    def disconnect(cls, connection: DataProviderConnection) -> bool:
        data = connection.data
        disconnected_fields = data.pop(cls.DISCONNECTED_DATA_FIELD, [])

        if not data or not connection.is_connected():
            return False

        disconnected_fields.append(data)
        connection.data = {cls.DISCONNECTED_DATA_FIELD: disconnected_fields}
        connection.save()
        return True

    @property
    def modules(self):
        return [ModuleChoices.PROCESS]

    def fetch_data(self, connection: DataProviderConnection):
        jira_config = JiraApiConfig(
            access_token=connection.data.get("access_token"),
            refresh_token=connection.data.get("refresh_token"),
            cloud_id=connection.data.get("cloud_id"),
        )
        self.init_api(config=jira_config, connection=connection)
        logger.info(f"Retrieving Jira projects for {connection.organization}...")
        projects = self.fetch_projects()
        logger.info(f"{len(projects)} projects found")
        for project_data in projects:
            self.process_project(project_data, connection)
        self.update_last_fetched(connection)

    def fetch_projects(self):
        return self.api.get_projects()

    def process_project(self, project_data: dict, connection: DataProviderConnection):
        project, created = DataProviderProject.objects.get_or_create(
            organization=connection.organization,
            provider=self.provider,
            external_id=project_data["id"],
            defaults={"name": project_data["name"], "meta": project_data},
        )

        if not created and project.name != project_data["name"] or project.meta != project_data:
            project.name = project_data["name"]
            project.meta = project_data
            project.save()

        # TODO move this call somewhere else
        self.get_or_update_jira_project(
            organization=connection.organization,
            project_data=project_data,
        )

    def get_or_update_jira_project(self, organization: Organization, project_data: dict) -> (JiraProject, bool):
        external_id = project_data["id"]

        project, created = JiraProject.objects.get_or_create(
            organization=organization,
            external_id=external_id,
            defaults={
                "name": project_data["name"],
                "key": project_data["key"],
            },
        )
        return project, created

    def get_base_jira_url(self, connection: DataProviderConnection):
        """
        Get the base Jira URL with caching support.

        Args:
            connection: DataProviderConnection to cache the URL

        Returns:
            The base Jira URL as a string
        """
        if not self.api:
            raise JiraApiException("Jira API not initialized")

        # If URL is cached, return it
        if connection and hasattr(connection, "data") and "base_jira_url" in connection.data:
            return connection.data["base_jira_url"]

        # Generate the URL
        # https://semalab.atlassian.net/browse/SIP-160
        base_url = self.api.get_organization_url()

        # Cache the URL if connection is provided
        if connection and hasattr(connection, "data"):
            connection.data["base_jira_url"] = base_url
            connection.save()

        return base_url

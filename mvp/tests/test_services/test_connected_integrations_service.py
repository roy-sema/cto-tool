from django.test import TestCase
from django.utils import timezone

from mvp.models import DataProvider, DataProviderConnection, Organization
from mvp.services.connected_integrations_service import ConnectedIntegrationsService


class ConnectedIntegrationsServiceTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Test Organization")

        self.github_provider = DataProvider.objects.create(name="GitHub")
        self.jira_provider = DataProvider.objects.create(name="Jira")

        self.github_connection = DataProviderConnection.objects.create(
            provider=self.github_provider,
            organization=self.organization,
            data={
                "installation_ids": ["123"],
                "disconnected_installation_ids": ["123"],
            },
            last_fetched_at=timezone.now(),
        )

    def test_get_connected_integration_statuses_returns_dict(self):
        DataProviderConnection.objects.create(
            provider=self.jira_provider,
            organization=self.organization,
            data={"installation_ids": [], "disconnected_installation_ids": ["123"]},
            last_fetched_at=None,
        )

        integration_map_keys = ["github", "jira"]
        result = ConnectedIntegrationsService.get_connected_integration_statuses(
            self.organization, integration_map_keys
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), {"github", "jira"})
        self.assertIsInstance(result["github"], dict)
        self.assertIsInstance(result["jira"], dict)
        self.assertEqual(result["github"]["status"], True)
        self.assertEqual(result["jira"]["status"], False)

    def test_get_connected_integration_statuses_filters_none_values(self):
        DataProviderConnection.objects.create(
            provider=self.jira_provider,
            organization=self.organization,
            data=None,
            last_fetched_at=None,
        )

        integration_map_keys = ["github", "jira"]
        result = ConnectedIntegrationsService.get_connected_integration_statuses(
            self.organization, integration_map_keys
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), {"github"})
        self.assertIsInstance(result["github"], dict)
        self.assertEqual(result["github"]["status"], True)

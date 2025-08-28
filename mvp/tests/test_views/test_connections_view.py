from django.urls import reverse

from mvp.models import MessageIntegration, MessageIntegrationServiceChoices, Organization
from mvp.tests.factories import create_organization_owner

from .base_view_test import BaseViewTestCase


class ConnectionsViewTest(BaseViewTestCase):
    def setUp(self):
        org_owner = create_organization_owner()
        self.organization = org_owner.organization
        self.user = org_owner.user

    @property
    def url(self):
        return reverse("connections")

    @staticmethod
    def get_integration_provider_by_name(providers, name):
        for provider in providers:
            if provider["name"] == name:
                return provider
        return None

    def test_ms_teams_connection_provider_displayed_when_not_connected(self):
        self.client.force_login(self.user)
        different_organization = Organization.objects.create(name="told.me")
        MessageIntegration.objects.create(
            organization=different_organization,
            data={"webhook_url": "test.com/url"},
            service=MessageIntegrationServiceChoices.MS_TEAMS,
            enabled=True,
        )
        with self.subTest("should display MS Teams connection in as not connected"):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            providers = response.context["providers"]
            ms_teams_provider = self.get_integration_provider_by_name(
                providers=providers,
                name=MessageIntegrationServiceChoices.MS_TEAMS.label,
            )
            self.assertIsNotNone(ms_teams_provider)
            self.assertFalse(ms_teams_provider["connected"])

    def test_ms_teams_connection_provider_displayed_when_connected(self):
        self.client.force_login(self.user)
        MessageIntegration.objects.create(
            organization=self.organization,
            data={"webhook_url": "test.com/url"},
            service=MessageIntegrationServiceChoices.MS_TEAMS,
            enabled=True,
        )
        with self.subTest("should display MS Teams connection in as connected"):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            providers = response.context["providers"]
            ms_teams_provider = self.get_integration_provider_by_name(
                providers=providers,
                name=MessageIntegrationServiceChoices.MS_TEAMS.label,
            )
            self.assertIsNotNone(ms_teams_provider)
            self.assertTrue(ms_teams_provider["connected"])

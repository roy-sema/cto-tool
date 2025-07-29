from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from compass.integrations.integrations import JiraIntegration
from mvp.models import (
    CustomUser,
    DataProviderConnection,
    DataProviderProject,
    Organization,
    OrgRole,
)
from mvp.tests.test_views.base_view_test import BaseViewTestCase


class BaseUpdateJiraProjectSelectionViewTest(BaseViewTestCase):
    def init(self, role: str, has_permission: bool):
        self.role = role
        self.has_permission = has_permission
        self.organization = Organization.objects.create(name="TestOrg")

        self.credentials = {"email": f"{role}_user@domain.com", "password": "testpass"}
        self.user = CustomUser.objects.create_user(**self.credentials)
        self.user.organizations.add(self.organization)

        group = Group.objects.get(name=role)
        self.user.groups.add(group)

        if has_permission:
            permission = Permission.objects.get(codename="can_view_compass_integrations")
            self.user.user_permissions.add(permission)

        provider = JiraIntegration().provider
        self.project = DataProviderProject.objects.create(
            name="Test Project",
            meta={},
            provider=provider,
            organization=self.organization,
        )
        self.connection = DataProviderConnection.objects.create(organization=self.organization, provider=provider)

        self.url = reverse(
            "compass_api_integrations_update_jira_project_selection",
            args=[self.project.id],
        )

    def login(self):
        logged_in = self.client.login(**self.credentials)
        self.assertTrue(logged_in)

    def perform_update(self, is_selected=True, project_id=None):
        data = {"is_selected": is_selected}
        project_id = project_id or self.project.id
        url = reverse("compass_api_integrations_update_jira_project_selection", args=[project_id])
        return self.client.put(url, data, content_type="application/json")


class TestUpdateJiraProjectSelectionViewOwner(BaseUpdateJiraProjectSelectionViewTest):
    def setUp(self):
        self.init(OrgRole.OWNER, has_permission=True)
        self.login()

    def test_successful_update(self):
        response = self.perform_update(is_selected=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "is_selected": True})
        self.project.refresh_from_db()
        self.assertTrue(self.project.meta.get("is_selected"))

    def test_missing_connection_returns_404(self):
        self.connection.delete()
        response = self.perform_update()
        self.assertEqual(response.status_code, 404)

    def test_project_not_found_returns_404(self):
        response = self.perform_update(project_id=999999)
        self.assertEqual(response.status_code, 404)

    def test_default_is_selected_false(self):
        response = self.client.put(self.url, {}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "is_selected": False})
        self.project.refresh_from_db()
        self.assertFalse(self.project.meta.get("is_selected"))


class TestUpdateJiraProjectSelectionViewWithoutPermission(BaseUpdateJiraProjectSelectionViewTest):
    def setUp(self):
        self.init(OrgRole.DEVELOPER, has_permission=False)
        self.login()

    def test_permission_denied(self):
        response = self.perform_update()
        self.assertEqual(response.status_code, 403)

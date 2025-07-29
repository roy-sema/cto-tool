from django.contrib.auth.models import Group
from django.urls import reverse

from mvp.models import (
    CustomUser,
    JiraProject,
    Organization,
    RepositoryGroup,
    RepositoryGroupCategoryChoices,
)

from .base_view_test import BaseViewTestCase


class RepositoryGroupEditViewTests(BaseViewTestCase):
    def setUp(self):
        self.credentials = {
            "email": "testuser@domain.com",
            "password": "testpass456",
        }

        self.organization = Organization.objects.create(name="TestOrg")
        self.user = CustomUser.objects.create_user(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

        self.repository_group = RepositoryGroup.objects.create(
            name="Test Group",
            usage_category=RepositoryGroupCategoryChoices.DEVELOPMENT,
            organization=self.organization,
        )
        self.not_selected_project = JiraProject.objects.create(
            name="TestProject1",
            organization=self.organization,
            external_id="1",
            is_selected=False,
        )

        self.selected_project = JiraProject.objects.create(
            name="TestProject2",
            organization=self.organization,
            external_id="2",
            is_selected=True,
        )

        self.selected_project.repository_group.add(self.repository_group)

        owner_group = Group.objects.get(name="Owner")
        owner_group.user_set.add(self.user)
        self.user.organizations.add(self.organization)

    def login(self):
        self.client.login(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

    def test_jira_projects_load(self):
        self.login()

        response = self.client.get(
            reverse(
                "repository_group_edit",
                kwargs={"pk_encoded": self.repository_group.public_id()},
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, self.selected_project.name)
        self.assertNotContains(response, self.not_selected_project.name)

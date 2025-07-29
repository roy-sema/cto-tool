from django.contrib.auth.models import Group
from django.urls import reverse

from mvp.models import CustomUser, Organization

from .base_view_test import BaseViewTestCase


class DashboardViewTests(BaseViewTestCase):
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

        owner_group = Group.objects.get(name="Owner")
        owner_group.user_set.add(self.user)
        self.user.organizations.add(self.organization)

    def login(self):
        self.client.login(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

    def test_load(self):
        self.login()

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "GenAI Codebase Composition")

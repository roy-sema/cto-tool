from django.urls import reverse

from mvp.tests.factories import create_organization_owner

from .base_view_test import BaseViewTestCase


class HomeViewTests(BaseViewTestCase):
    def setUp(self):
        org_owner = create_organization_owner()
        self.user = org_owner.user
        self.organization = org_owner.organization

    def login(self):
        self.client.force_login(self.user)

    def test_load(self):
        self.login()

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, '<div id="vue-app"></div>')

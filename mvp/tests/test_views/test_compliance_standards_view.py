from django.contrib.auth.models import Group

from mvp.models import (
    ComplianceStandard,
    ComplianceStandardReference,
    ComplianceStandardStatusChoices,
    CustomUser,
    Industry,
    Organization,
)

from .base_view_test import BaseViewTestCase


class ComplianceStandardsViewTests(BaseViewTestCase):
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

        industries = Industry.objects.all()

        self.standard1 = ComplianceStandard.objects.create(
            name="Standard 1",
            status=ComplianceStandardStatusChoices.PROPOSED,
            description="Description 1",
            updated_at="2023-01-01",
        )
        self.standard2 = ComplianceStandard.objects.create(
            name="Standard 2",
            status=ComplianceStandardStatusChoices.CONTEMPLATED,
            description="Description 2",
            updated_at="2023-01-02",
        )

        self.standard3 = ComplianceStandard.objects.create(
            name="Standard 3",
            status=ComplianceStandardStatusChoices.FULLY_IMPLEMENTED,
            description="Description 3",
            updated_at="2023-01-03",
            is_excluded=True,
        )

        self.standard1.industries.add(industries[0])
        self.standard2.industries.add(industries[1])

        self.standard1.save()
        self.standard2.save()

        self.ref1 = ComplianceStandardReference.objects.create(
            text="Link 1", url="http://link1.com", standard=self.standard1
        )
        self.ref2 = ComplianceStandardReference.objects.create(
            text="Link 2", url="http://link2.com", standard=self.standard2
        )

    def login(self):
        self.client.login(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

    def assertComponentsExist(self, response):
        self.assertContains(response, self.standard1.name)
        self.assertContains(response, self.standard2.name)
        self.assertNotContains(response, self.standard3.name)
        self.assertContains(response, self.ref1.url)
        self.assertContains(response, self.ref2.url)

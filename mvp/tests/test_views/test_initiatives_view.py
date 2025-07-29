import json

from django.contrib.auth.models import Group
from django.urls import reverse

from compass.contextualization.models import Initiative, InitiativeEpic, Roadmap
from mvp.models import CustomUser, Organization

from .base_view_test import BaseViewTestCase


class InitiativesSettingsViewTest(BaseViewTestCase):
    def setUp(self):
        self.credentials = {
            "staff": {
                "email": "teststaff@domain.com",
                "password": "testpass123",
            },
            "user": {
                "email": "testuser@domain.com",
                "password": "testpass456",
            },
        }

        self.staff = CustomUser.objects.create_user(
            email=self.credentials["staff"]["email"],
            password=self.credentials["staff"]["password"],
            is_staff=True,
        )

        self.user = CustomUser.objects.create_user(
            email=self.credentials["user"]["email"],
            password=self.credentials["user"]["password"],
        )

        self.users = {
            "staff": self.staff,
            "user": self.user,
        }

        self.organizations = {
            "staff": Organization.objects.create(name="StaffOrg"),
            "user": Organization.objects.create(name="UserOrg"),
        }

        self.staff.organizations.add(self.organizations["staff"])
        self.user.organizations.add(self.organizations["user"])

        self.roadmaps = {
            "staff": Roadmap.objects.create(
                organization=self.organizations["staff"],
                start_date="2024-01-01",
                end_date="2024-01-15",
                day_interval=14,
            ),
            "user": Roadmap.objects.create(
                organization=self.organizations["user"],
                start_date="2024-01-01",
                end_date="2024-01-15",
                day_interval=14,
            ),
        }

        self.initiatives = {
            "staff": Initiative.objects.create(
                name="Staff Initiative 1",
                roadmap=self.roadmaps["staff"],
                pinned=False,
                disabled=False,
            ),
            "user": Initiative.objects.create(
                name="User Initiative 1",
                roadmap=self.roadmaps["user"],
                pinned=True,
                disabled=False,
            ),
        }

        self.epics = {
            "staff": InitiativeEpic.objects.create(
                name="Staff Epic 1",
                initiative=self.initiatives["staff"],
                pinned=False,
                disabled=False,
            ),
            "user": InitiativeEpic.objects.create(
                name="User Epic 1",
                initiative=self.initiatives["user"],
                pinned=True,
                disabled=False,
            ),
        }

        self.owner_group = Group.objects.get(name="Owner")
        self.owner_group.user_set.add(self.staff)
        self.owner_group.user_set.add(self.user)

    def login(self, user_type):
        self.client.login(
            email=self.credentials[user_type]["email"],
            password=self.credentials[user_type]["password"],
        )

    def make_payload(self, user_key, updates):
        initiative = self.initiatives[user_key]
        epic = self.epics[user_key]
        return {
            "initiatives": [
                {
                    "id": initiative.id,
                    "pinned": updates.get("initiative_pinned", initiative.pinned),
                    "disabled": updates.get("initiative_disabled", initiative.disabled),
                    "custom_name": updates.get("initiative_custom_name", initiative.custom_name or ""),
                    "epics": [
                        {
                            "id": epic.id,
                            "pinned": updates.get("epic_pinned", epic.pinned),
                            "disabled": updates.get("epic_disabled", epic.disabled),
                            "custom_name": updates.get("epic_custom_name", epic.custom_name or ""),
                        }
                    ],
                }
            ]
        }

    def post_payload(self, user_key, updates):
        self.login(user_key)
        payload = self.make_payload(user_key, updates)
        return self.client.post(reverse("initiatives"), data={"payload": json.dumps(payload)})

    def test_post_pin_initiative(self):
        self.assertFalse(self.initiatives["staff"].pinned)
        self.post_payload("staff", {"initiative_pinned": True})
        self.initiatives["staff"].refresh_from_db()
        self.assertTrue(self.initiatives["staff"].pinned)

    def test_post_unpin_initiative(self):
        self.assertTrue(self.initiatives["user"].pinned)
        self.post_payload(
            "user",
            {"initiative_pinned": False, "initiative_custom_name": "Updated Name"},
        )
        self.initiatives["user"].refresh_from_db()
        self.assertFalse(self.initiatives["user"].pinned)
        self.assertEqual(self.initiatives["user"].custom_name, "Updated Name")

    def test_post_disable_initiative(self):
        self.assertFalse(self.initiatives["staff"].disabled)
        self.post_payload("staff", {"initiative_disabled": True})
        self.initiatives["staff"].refresh_from_db()
        self.assertTrue(self.initiatives["staff"].disabled)

    def test_post_pin_epic(self):
        self.assertFalse(self.epics["staff"].pinned)
        self.post_payload("staff", {"epic_pinned": True})
        self.epics["staff"].refresh_from_db()
        self.assertTrue(self.epics["staff"].pinned)

    def test_post_unpin_epic(self):
        self.assertTrue(self.epics["user"].pinned)
        self.post_payload("user", {"epic_pinned": False, "epic_custom_name": "Updated Epic Name"})
        self.epics["user"].refresh_from_db()
        self.assertFalse(self.epics["user"].pinned)
        self.assertEqual(self.epics["user"].custom_name, "Updated Epic Name")

    def test_post_disable_epic(self):
        self.assertFalse(self.epics["staff"].disabled)
        self.post_payload("staff", {"epic_disabled": True})
        self.epics["staff"].refresh_from_db()
        self.assertTrue(self.epics["staff"].disabled)

    def test_post_update_custom_names(self):
        self.post_payload(
            "staff",
            {
                "initiative_custom_name": "Custom Initiative Name",
                "epic_custom_name": "Custom Epic Name",
            },
        )
        self.initiatives["staff"].refresh_from_db()
        self.epics["staff"].refresh_from_db()
        self.assertEqual(self.initiatives["staff"].custom_name, "Custom Initiative Name")
        self.assertEqual(self.epics["staff"].custom_name, "Custom Epic Name")

    def test_post_multiple_updates(self):
        self.post_payload(
            "user",
            {
                "initiative_pinned": True,
                "initiative_disabled": True,
                "initiative_custom_name": "Updated Initiative",
                "epic_pinned": True,
                "epic_custom_name": "Updated Epic",
            },
        )
        self.initiatives["user"].refresh_from_db()
        self.epics["user"].refresh_from_db()
        self.assertTrue(self.initiatives["user"].pinned)
        self.assertTrue(self.initiatives["user"].disabled)
        self.assertEqual(self.initiatives["user"].custom_name, "Updated Initiative")
        self.assertTrue(self.epics["user"].pinned)
        self.assertEqual(self.epics["user"].custom_name, "Updated Epic")

    def test_post_epic_parent_disabled_handling(self):
        self.post_payload("staff", {"initiative_disabled": True})
        self.post_payload(
            "staff",
            {"epic_pinned": True, "epic_custom_name": "Epic After Parent Disabled"},
        )
        self.epics["staff"].refresh_from_db()
        self.assertTrue(self.epics["staff"].pinned)
        self.assertEqual(self.epics["staff"].custom_name, "Epic After Parent Disabled")

    def test_success_message_displayed(self):
        self.login("staff")
        payload = self.make_payload("staff", {"initiative_pinned": True})
        response = self.client.post(reverse("initiatives"), data={"payload": json.dumps(payload)}, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("Initiatives and Epics updated!" in str(m) for m in messages))

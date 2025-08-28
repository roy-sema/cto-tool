from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.urls import reverse

from mvp.models import (
    CustomUser,
    Organization,
    Rule,
    RuleCondition,
    RuleConditionCodeTypeChoices,
    RuleConditionModeChoices,
    RuleConditionOperatorChoices,
    RuleRiskChoices,
    UserInvitation,
)
from mvp.views import UsersView

from .base_view_test import BaseViewTestCase


class MembersViewTest(BaseViewTestCase):
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

        self.owner_group = Group.objects.get(name="Owner")
        self.owner_group.user_set.add(self.staff)
        self.owner_group.user_set.add(self.user)

        self.organizations = {
            "staff": Organization.objects.create(name="StaffOrg"),
            "user": Organization.objects.create(name="UserOrg"),
        }

        self.staff.organizations.add(self.organizations["staff"])
        self.user.organizations.add(self.organizations["user"])

        self.payload_invite_base = {
            "action": "invite_member",
            "first_name": "Invitee",
            "last_name": "Test",
            "email": "testinvite@domain.com",
            "role": self.owner_group.pk,
        }

        preset_rule = Rule.objects.create(
            name="TestPresetRule",
            condition_mode=RuleConditionModeChoices.ALL,
            risk=RuleRiskChoices.HIGH,
            is_preset=True,
        )
        RuleCondition.objects.create(
            rule=preset_rule,
            code_type=RuleConditionCodeTypeChoices.AI,
            operator=RuleConditionOperatorChoices.EQUAL,
            percentage=50,
        )

        self.preset_rules = Rule.objects.filter(is_preset=True)

        # create this rule to make sure we are only copying preset rules
        self.org_rule = Rule.objects.create(
            name="TestOrgRule",
            condition_mode=RuleConditionModeChoices.ALL,
            risk=RuleRiskChoices.HIGH,
            is_preset=False,
            organization=self.organizations["staff"],
        )
        RuleCondition.objects.create(
            rule=self.org_rule,
            code_type=RuleConditionCodeTypeChoices.AI,
            operator=RuleConditionOperatorChoices.EQUAL,
            percentage=50,
        )

    def login(self, user_type):
        self.client.login(
            email=self.credentials[user_type]["email"],
            password=self.credentials[user_type]["password"],
        )

    def create_invitation(self, user_type):
        return UserInvitation.objects.create(
            email=f"invitee_{user_type}@domain.com",
            sent_by=self.users[user_type],
            organization=self.organizations[user_type],
            role=self.owner_group,
        )

    def test_user_member_list(self):
        invitation_same_org = self.create_invitation("user")
        invitation_other_org = self.create_invitation("staff")

        self.login("user")

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, invitation_same_org.email)
        self.assertNotContains(response, invitation_other_org.email)

    def test_staff_member_list(self):
        invitation_same_org = self.create_invitation("staff")
        invitation_other_org = self.create_invitation("user")

        self.login("staff")

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, invitation_same_org.email)
        self.assertContains(response, invitation_other_org.email)

    def test_user_form(self):
        self.login("user")

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, '<label for="id_organization"')
        self.assertNotContains(response, '<label for="id_new_organization_name"')

    def test_staff_form(self):
        self.login("staff")

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, '<label for="id_organization"')
        self.assertContains(response, '<label for="id_new_organization_name"')

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_user_invite_member_valid(self, mock_send_invitation_mail):
        self.login("user")

        payload = {
            **self.payload_invite_base,
            # attempting a different organization
            "organization": self.organizations["staff"].pk,
        }
        response = self.client.post(reverse("users"), data=payload)

        self.assertTrue(
            UserInvitation.objects.filter(
                email=payload["email"],
                # we get same organization as the user regardless of payload
                organization=self.organizations["user"],
                role=self.owner_group,
            ).exists()
        )

        self.assertTrue(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users')}#{UsersView.ANCHOR_PENDING_INVITES}")

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), UsersView.MESSAGE_INVITATION_SENT)

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_staff_invite_member_existing_organization_valid(self, mock_send_invitation_mail):
        self.login("staff")

        payload = {
            **self.payload_invite_base,
            # different organization, but existing
            "organization": self.organizations["user"].pk,
        }
        response = self.client.post(reverse("users"), data=payload)

        self.assertTrue(
            UserInvitation.objects.filter(
                email=payload["email"],
                organization=self.organizations["user"],
                role=self.owner_group,
            ).exists()
        )

        self.assertTrue(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users')}#{UsersView.ANCHOR_PENDING_INVITES}")

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), UsersView.MESSAGE_INVITATION_SENT)

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_staff_invite_member_new_organization_valid(self, mock_send_invitation_mail):
        self.login("staff")

        payload = {
            **self.payload_invite_base,
            # attempting a new organization
            "new_organization_name": "NewOrg",
        }
        response = self.client.post(reverse("users"), data=payload)

        self.assertTrue(Organization.objects.filter(name=payload["new_organization_name"]).exists())

        org = Organization.objects.get(name=payload["new_organization_name"])
        rules = org.rule_set_non_global()
        self.assertEqual(rules.count(), self.preset_rules.count())
        self.assertFalse(rules[0].is_preset)
        self.assertFalse(rules[0].apply_organization)

        rule_ids = rules.values_list("id", flat=True)
        preset_rule_ids = self.preset_rules.values_list("id", flat=True)
        for rule_id in rule_ids:
            self.assertNotIn(rule_id, preset_rule_ids)

        self.assertTrue(
            UserInvitation.objects.filter(
                email=payload["email"],
                organization__name=payload["new_organization_name"],
                role=self.owner_group,
            ).exists()
        )

        self.assertTrue(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users')}#{UsersView.ANCHOR_PENDING_INVITES}")

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), UsersView.MESSAGE_INVITATION_SENT)

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_staff_both_organization_fields_invalid(self, mock_send_invitation_mail):
        self.login("staff")

        payload = {
            **self.payload_invite_base,
            # attempting both existing and new organizations
            "organization": self.organizations["user"].pk,
            "new_organization_name": "NewOrg",
        }
        response = self.client.post(reverse("users"), data=payload)

        self.assertFalse(UserInvitation.objects.filter(email=payload["email"]).exists())

        self.assertFalse(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        non_field_errors = form.non_field_errors()
        self.assertIn(
            "Please select an existing organization or provide a name for a new one, not both.",
            non_field_errors,
        )

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_staff_no_organization_invalid(self, mock_send_invitation_mail):
        self.login("staff")

        payload = {
            **self.payload_invite_base,
            # attempting no organizations
        }
        response = self.client.post(reverse("users"), data=payload)

        self.assertFalse(UserInvitation.objects.filter(email=payload["email"]).exists())

        self.assertFalse(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        non_field_errors = form.non_field_errors()
        self.assertIn(
            "Please select an existing organization or provide a name for a new one.",
            non_field_errors,
        )

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_invite_member_already_exists(self, mock_send_invitation_mail):
        self.login("user")

        payload = {
            **self.payload_invite_base,
            "email": self.credentials["staff"]["email"],
            "organization": self.organizations["user"].pk,
        }
        response = self.client.post(reverse("users"), data=payload)

        self.assertFalse(UserInvitation.objects.filter(email=payload["email"]).exists())

        self.assertFalse(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        self.assertIn("A user with this email already exists.", form.errors["email"])

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_user_resend_invitation_valid(self, mock_send_invitation_mail):
        invitation = self.create_invitation("user")

        self.login("user")

        payload = {
            "action": "resend_invitation",
            "invitation_id": invitation.public_id(),
        }

        response = self.client.post(reverse("users"), payload)

        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.resent_at)

        self.assertTrue(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users')}#{UsersView.ANCHOR_PENDING_INVITES}")

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), UsersView.MESSAGE_INVITATION_RESENT)

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_staff_resend_invitation_valid(self, mock_send_invitation_mail):
        # different organization invite
        invitation = self.create_invitation("user")

        self.login("staff")

        payload = {
            "action": "resend_invitation",
            "invitation_id": invitation.public_id(),
        }

        response = self.client.post(reverse("users"), payload)

        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.resent_at)

        self.assertTrue(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users')}#{UsersView.ANCHOR_PENDING_INVITES}")

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), UsersView.MESSAGE_INVITATION_RESENT)

    def test_new_organization_default_flags_limits(self):
        self.login("staff")

        payload = {
            **self.payload_invite_base,
            # attempting a new organization
            "new_organization_name": "NewOrg",
        }
        self.client.post(reverse("users"), data=payload)

        org = Organization.objects.get(name=payload["new_organization_name"])

        self.assertEqual(org.status_check_enabled, settings.DEFAULT_FLAG_STATUS_CHECK_ENABLED)

        self.assertEqual(org.analysis_max_scans, settings.DEFAULT_LIMIT_SCANS)
        self.assertEqual(org.analysis_max_repositories, settings.DEFAULT_LIMIT_REPOSITORIES)
        self.assertEqual(
            org.analysis_max_lines_per_repository,
            settings.DEFAULT_LIMIT_LINES_PER_REPOSITORY,
        )

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_bulk_invite_valid(self, mock_send_invitation_mail):
        self.login("user")

        emails = ["test1@domain.com", "test2@domain.com"]

        payload = {
            "action": "bulk_invite",
            "role": self.owner_group.pk,
            "emails": ",".join(emails),
        }
        response = self.client.post(reverse("users"), data=payload)

        for email in emails:
            self.assertTrue(
                UserInvitation.objects.filter(
                    email=email,
                    organization=self.organizations["user"],
                    role=self.owner_group,
                ).exists()
            )

        self.assertEqual(mock_send_invitation_mail.call_count, len(emails))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users')}#{UsersView.ANCHOR_PENDING_INVITES}")

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), UsersView.MESSAGE_INVITATIONS_SENT)

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_bulk_invite_invalid(self, mock_send_invitation_mail):
        self.login("user")

        invalid_email = "xyz"
        emails = ["test1@domain.com", invalid_email]

        payload = {
            "action": "bulk_invite",
            "role": self.owner_group.pk,
            "emails": ",".join(emails),
        }
        response = self.client.post(reverse("users"), data=payload)

        for email in emails:
            self.assertFalse(UserInvitation.objects.filter(email=email).exists())

        self.assertFalse(mock_send_invitation_mail.called)

        self.assertEqual(response.status_code, 200)

        form = response.context["bulk_form"]
        email_errors = form.errors.get("emails")
        self.assertIn(f"{invalid_email} is not a valid email address", email_errors)

    @patch("mvp.views.UsersView.send_invitation_mail")
    def test_staff_create_new_organization_sets_created_by(self, mock_send_invitation_mail):
        self.login("staff")
        payload = {
            **self.payload_invite_base,
            "new_organization_name": "NewOrgWithCreatedBy",
        }
        with self.subTest("should set created_by field when staff invites a user to a new organization"):
            self.client.post(reverse("users"), data=payload)
            org = Organization.objects.get(name=payload["new_organization_name"])
            self.assertEqual(org.created_by, self.staff)

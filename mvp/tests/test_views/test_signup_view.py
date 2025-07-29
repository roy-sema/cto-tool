from django.conf import settings
from django.contrib.auth.models import Group
from django.urls import reverse
from parameterized import parameterized

from mvp.models import CustomUser, Organization, UserInvitation
from mvp.views import SignUpView

from .base_view_test import BaseViewTestCase


class SignUpViewTest(BaseViewTestCase):
    def setUp(self):
        self.credentials = {"email": "testuser@domain.com", "password": "testpass456"}
        self.staff = CustomUser.objects.create_user(
            email=self.credentials["email"],
            password=self.credentials["password"],
            is_staff=True,
        )

        self.owner_group = Group.objects.get(name="Owner")
        self.owner_group.user_set.add(self.staff)

        self.organizations = {
            "staff": Organization.objects.create(name="StaffOrg"),
            "user": Organization.objects.create(name="UserOrg"),
        }

        self.staff.organizations.add(self.organizations["staff"])

        self.payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password1": "securepassword123",
            "password2": "securepassword123",
            "accept_terms": "on",
        }

        self.invitation = UserInvitation.objects.create(
            first_name=self.payload["first_name"],
            last_name=self.payload["last_name"],
            email=self.payload["email"],
            sent_by=self.staff,
            organization=self.organizations["user"],
            role=self.owner_group,
        )

    def test_logout_first(self):
        self.client.login(email=self.credentials["email"], password=self.credentials["password"])

        response = self.client.get(settings.LOGIN_REDIRECT_URL)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        response = self.client.get(f"{reverse('signup')}?invite={self.invitation.token}")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_valid_invite_token(self):
        response = self.client.get(f"{reverse('signup')}?invite={self.invitation.token}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.invitation.first_name)
        self.assertContains(response, self.invitation.last_name)
        self.assertContains(response, self.invitation.email)

        form = response.context["form"]
        self.assertEqual(self.invitation.first_name, form.initial["first_name"])
        self.assertEqual(self.invitation.last_name, form.initial["last_name"])
        self.assertEqual(self.invitation.email, form.initial["email"])

    def test_invalid_invite_token(self):
        response = self.client.get(f"{reverse('signup')}?invite=invalidtoken")

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("account_login"))

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), SignUpView.MESSAGE_INVALID_LINK)

    def test_no_invite_token(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        self.assertFalse(form.initial)

    def test_signup_with_invite_valid(self):
        response = self.client.post(
            f"{reverse('signup')}?invite={self.invitation.token}",
            self.payload,
            follow=True,
        )

        user = CustomUser.objects.get(email=self.payload["email"])

        self.assertTrue(user)
        self.assertTrue(user.groups.exists())
        self.assertTrue(user.organizations.exists())

        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.is_deleted)

        self.assertRedirects(response, "/onboarding/welcome")

    def test_signup_with_invite_valid_redirect(self):
        organization = Organization.objects.create(name="TestOrg")

        self.payload["email"] = "test@domain.com"

        invitation = UserInvitation.objects.create(
            first_name=self.payload["first_name"],
            last_name=self.payload["last_name"],
            email=self.payload["email"],
            sent_by=self.staff,
            organization=organization,
            role=self.owner_group,
        )

        response = self.client.post(
            f"{reverse('signup')}?invite={invitation.token}",
            self.payload,
            follow=True,
        )

        self.assertRedirects(response, "/onboarding/welcome")

    def test_signup_with_invite_valid_different_email(self):
        other_email = "invitee@domain.com"
        other_email_invitation = UserInvitation.objects.create(
            first_name=self.payload["first_name"],
            last_name=self.payload["last_name"],
            email=other_email,
            sent_by=self.staff,
            organization=self.organizations["user"],
            role=self.owner_group,
        )

        response = self.client.post(
            f"{reverse('signup')}?invite={self.invitation.token}",
            {**self.payload, "email": other_email},
            follow=True,
        )

        user = CustomUser.objects.get(email=other_email)

        self.assertTrue(user)
        self.assertTrue(user.groups.exists())
        self.assertTrue(user.organizations.exists())

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email=self.payload["email"])

        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.is_deleted)

        other_email_invitation.refresh_from_db()
        self.assertTrue(other_email_invitation.is_deleted)

        self.assertRedirects(response, "/onboarding/welcome")

    def test_signup_with_invite_invalid(self):
        response = self.client.post(f"{reverse('signup')}?invite=invalidtoken", self.payload)

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email=self.payload["email"])

        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("account_login"))

        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), SignUpView.MESSAGE_INVALID_LINK)

    def test_signup_without_invite(self):
        payload = {
            **self.payload,
            "organization_name": "Example",
        }
        response = self.client.post(reverse("signup"), payload, follow=True)

        user = CustomUser.objects.get(email=self.payload["email"])

        self.assertTrue(user)
        self.assertEqual(user.role(), self.owner_group)
        self.assertEqual(user.organizations.count(), 1)
        self.assertEqual(user.organizations.first().name, payload["organization_name"])
        self.assertEqual(user.initials, "JD")

        self.assertRedirects(response, "/onboarding/welcome")

    def test_terms_not_accepted_with_invite(self):
        response = self.client.post(
            f"{reverse('signup')}?invite={self.invitation.token}",
            {**self.payload, "accept_terms": ""},
        )

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email=self.payload["email"])

        self.invitation.refresh_from_db()
        self.assertFalse(self.invitation.is_deleted)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_terms_not_accepted_without_invite(self):
        response = self.client.post(reverse("signup"), {**self.payload, "accept_terms": ""})

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email=self.payload["email"])

        self.invitation.refresh_from_db()
        self.assertFalse(self.invitation.is_deleted)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    @parameterized.expand(
        [
            ({},),  # missing organization name
        ]
    )
    def test_signup_without_company_fields(self, extra_payload):
        payload = {
            **self.payload,
            **extra_payload,
        }
        response = self.client.post(reverse("signup"), payload, follow=True)

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email=self.payload["email"])

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    @parameterized.expand(
        [
            ("on", True),
            ("", True),
            ("on", False),
            ("", False),
        ]
    )
    def test_consent_marketing_notifications(self, consent, with_invite):
        self.invitation.refresh_from_db()

        url = reverse("signup")
        payload = {**self.payload, "consent_marketing_notifications": consent}

        if with_invite:
            url += f"?invite={self.invitation.token}"
        else:
            payload["organization_name"] = "Example"

        response = self.client.post(url, payload)
        user = CustomUser.objects.get(email=self.payload["email"])

        self.assertTrue(user)
        self.assertEqual(user.consent_marketing_notifications, consent == "on")

        self.assertEqual(response.status_code, 302)

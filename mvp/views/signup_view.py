import logging

import posthog
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import generic
from sentry_sdk import capture_exception, push_scope

from compass.integrations.integrations import MailChimpIntegration
from mvp.forms import CustomUserCreationForm, InviteUserForm
from mvp.models import Organization, UserInvitation
from mvp.utils import start_new_thread, traceback_on_debug

logger = logging.getLogger(__name__)


class SignUpView(generic.CreateView):
    success_url = reverse_lazy("account_login")
    template_name = "account/signup.html"

    MESSAGE_INVALID_LINK = (
        "This invitation link has already been used or it's invalid. Please check your email or request a new invite."
    )
    # This message is purposely misleading to frustrate blocked users
    MESSAGE_SIGNUP_BLOCKED = "The passwords don't match. Please make sure they are exactly the same."

    HOME_PAGE_REDIRECT = "/home"
    WELCOME_PAGE_REDIRECT = "/onboarding/welcome"

    def get(self, request, *args, **kwargs):
        signup_url = reverse_lazy("signup")

        invite_token = self.get_invite_token(request)
        if invite_token:
            try:
                invitation = self.get_invitation(invite_token)
            except UserInvitation.DoesNotExist:
                return self.handle_invalid_invitation(request)

            logout(request)

            form_data = {
                "first_name": invitation.first_name,
                "last_name": invitation.last_name,
                "email": invitation.email,
            }
            form = InviteUserForm(initial=form_data)
            signup_url = f"{signup_url}?invite={invite_token}"

            posthog.capture(invitation.email, event="access_invite")
        else:
            form = CustomUserCreationForm()

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "invite_token": invite_token,
                "url": signup_url,
            },
        )

    def post(self, request, *args, **kwargs):
        invite_token = self.get_invite_token(request)
        if invite_token:
            form = InviteUserForm(request.POST)
        else:
            form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            if self.is_blocked_email(form.cleaned_data["email"]):
                messages.error(request, self.MESSAGE_SIGNUP_BLOCKED)
                return render(request, self.template_name, {"form": form})

            user = form.save(commit=False)
            organization_name = form.cleaned_data.get("organization_name")

            try:
                self.save_form(user, request, organization_name)
            except UserInvitation.DoesNotExist:
                return self.handle_invalid_invitation(request)

            if invite_token:
                posthog.capture(user.email, event="accept_invite")

            posthog.capture(
                user.email,
                event="signup",
                properties={
                    "$set": {
                        "company_url": user.company_url,
                        "company_number_of_developers": user.company_number_of_developers,
                    }
                },
            )

            # TODO: send an email to verify the address
            login(
                request,
                user,
                backend="allauth.account.auth_backends.AuthenticationBackend",
            )

            onboarding_completed = user.organizations.filter(onboarding_completed=True).exists()
            redirect_page = self.HOME_PAGE_REDIRECT if onboarding_completed else self.WELCOME_PAGE_REDIRECT
            return redirect(redirect_page)

        return render(
            request,
            self.template_name,
            {"form": form, "invite_token": invite_token},
        )

    @transaction.atomic
    def save_form(self, user, request, organization_name=None):
        # Reset flags in case an attacker tries to set them
        user.is_staff = False
        user.is_superuser = False
        user.initials = user.generate_initials_from_names(user.first_name, user.last_name)
        user.save()

        invite_token = self.get_invite_token(request)
        if invite_token:
            invitation = self.get_invitation(invite_token)

            invitation.role.user_set.add(user)
            invitation.organization.customuser_set.add(user)

            # users can change their email on the signup form,
            # so we delete pending invitations to that email too
            if invitation.email != user.email:
                UserInvitation.objects.filter(email=user.email).delete()

            invitation.delete()
        else:
            # Users that sign up become owners by default
            owner_group = Group.objects.get(name="Owner")
            owner_group.user_set.add(user)

            # Create an organization for the user
            org = Organization(name=organization_name)
            org.set_default_flags()
            org.set_default_limits()
            org.save()

            # Add the user to the organization
            org.customuser_set.add(user)

            # Copy the default rules to the organization
            org.copy_preset_rules()

            transaction.on_commit(lambda: self.send_welcome_email_background(user))

    def get_invite_token(self, request):
        return request.GET.get("invite")

    def get_invitation(self, token):
        try:
            return UserInvitation.objects.get(token=token)
        except (UserInvitation.DoesNotExist, ValidationError) as error:
            traceback_on_debug()

            with push_scope() as scope:
                try:
                    invitation = UserInvitation.deleted_objects.get(token=token)
                    scope.set_extra("invitation", invitation.email)
                    scope.set_extra("organization", invitation.organization.name)
                except (UserInvitation.DoesNotExist, ValidationError):
                    scope.set_extra("invitation", "unknown")
                    pass

                capture_exception(error)
                raise UserInvitation.DoesNotExist

    def handle_invalid_invitation(self, request):
        messages.error(request, self.MESSAGE_INVALID_LINK)
        return redirect("account_login")

    def is_blocked_email(self, email):
        return any(text in email for text in settings.BLOCKED_EMAIL_TEXTS)

    @start_new_thread
    def send_welcome_email_background(self, user):
        if not settings.MAILCHIMP_ACTIVE:
            logger.warning("Mailchimp is not active. Skipping sending welcome email.")
            return

        MailChimpIntegration().sync_user_on_sign_up(user)

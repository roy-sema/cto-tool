import logging

import posthog
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.html import strip_tags
from django.views import View

from mvp.forms import BulkInviteForm, UserInvitationForm
from mvp.mixins import DecodePublicIdMixin
from mvp.models import CustomUser, Group, OrgRole, UserInvitation
from mvp.services import EmailService

logger = logging.getLogger(__name__)


class UsersView(LoginRequiredMixin, DecodePublicIdMixin, PermissionRequiredMixin, View):
    permission_required = "mvp.can_edit_members"

    ANCHOR_PENDING_INVITES = "pending-invites"

    MESSAGE_INVITATION_SENT = "Invitation sent!"
    MESSAGE_INVITATION_RESENT = "Invitation re-sent!"
    MESSAGE_INVITATION_NOT_FOUND = "Invitation not found!"

    MESSAGE_INVITATIONS_SENT = "Invitations sent!"

    MESSAGE_USER_DELETED = "User removed"
    MESSAGE_USER_NO_SELF_DELETE = "You can't remove yourself!"
    MESSAGE_USER_NOT_FOUND = "User not found!"

    MESSAGE_UNKNOWN_ACTION = "Unrecognized action!"

    MESSAGE_GROUP_NOT_FOUND = "Invalid Role!"
    MESSAGE_GROUP_NO_CHANGE_OWNER = "You can't change the role of an owner"
    MESSAGE_GROUP_NO_SELF_CHANGE = "You can't change yourself!"  # lol

    def get(self, request):
        return self.render_page(request, UserInvitationForm(request=request), BulkInviteForm())

    def post(self, request):
        action = request.POST.get("action")

        if action == "invite_member":
            return self.invite_member(request)

        if action == "bulk_invite":
            return self.bulk_invite(request)

        if action == "resend_invitation":
            return self.resend_invitation(request)

        if action == "delete_member":
            return self.delete_member(request)

        if action == "update_member_role":
            return self.update_member_role(request)

        messages.error(request, self.MESSAGE_UNKNOWN_ACTION)
        return self.redirect_to_view(request)

    def invite_member(self, request):
        form = UserInvitationForm(request.POST, request=request)

        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.sent_by = request.user
            invitation.save()
            self.send_invitation_mail(request, invitation)

            posthog.capture(
                request.user.email,
                event=("send_invite_staff" if request.user.is_staff else "send_invite_user"),
            )

            messages.success(request, self.MESSAGE_INVITATION_SENT)
            return self.redirect_to_view(request, invites_section=True)

        return self.render_page(request, form, BulkInviteForm())

    def bulk_invite(self, request):
        form = BulkInviteForm(request.POST)

        if form.is_valid():
            emails = form.cleaned_data["emails"]
            role_id = form.cleaned_data["role"]
            role = Group.objects.get(id=role_id)
            for email in emails:
                try:
                    invitation = UserInvitation.objects.create(
                        email=email,
                        first_name="",
                        last_name="",
                        role=role,
                        organization=request.current_organization,
                        sent_by=request.user,
                    )
                    self.send_invitation_mail(request, invitation)
                except Exception:
                    logger.exception(
                        "Failed to invite user",
                        extra={"email": email, "user_trying_to_invite": request.user},
                    )

            posthog.capture(request.user.email, event=("send_bulk_invite"))

            messages.success(request, self.MESSAGE_INVITATIONS_SENT)
            return self.redirect_to_view(request, invites_section=True)

        return self.render_page(request, UserInvitationForm(request=request), form)

    def resend_invitation(self, request):
        invitation_id = self.decode_id(request.POST.get("invitation_id"))
        try:
            current_org = request.current_organization

            # make sure user has access to this invitation
            conditions = {"pk": invitation_id}
            if not request.user.is_authenticated:
                conditions["organization"] = current_org

            invitation = UserInvitation.objects.get(**conditions)
            invitation.resent_at = timezone.now()
            invitation.save()

            self.send_invitation_mail(request, invitation)
            messages.success(request, self.MESSAGE_INVITATION_RESENT)
        except UserInvitation.DoesNotExist:
            messages.error(request, self.MESSAGE_INVITATION_NOT_FOUND)

        return self.redirect_to_view(request, invites_section=True)

    def delete_member(self, request):
        user_id = self.decode_id(request.POST.get("member_id"))
        try:
            current_org = request.current_organization
            user = CustomUser.objects.get(pk=user_id, organizations__in=[current_org])
            if user != request.user:
                user.remove_from_organization(current_org)
                messages.success(request, self.MESSAGE_USER_DELETED)
            else:
                messages.error(request, self.MESSAGE_USER_NO_SELF_DELETE)
        except CustomUser.DoesNotExist:
            messages.error(request, self.MESSAGE_USER_NOT_FOUND)

        return self.redirect_to_view(request)

    def update_member_role(self, request):
        user_id = self.decode_id(request.POST.get("member_id"))
        try:
            current_org = request.current_organization
            group_id = int(request.POST.get("role"))
            user = CustomUser.objects.get(pk=user_id, organizations__in=[current_org])

            # written in reverse order to have errors at the bottom
            if user != request.user and not user.is_owner():
                new_group = Group.objects.get(pk=group_id)
                user.groups.first().user_set.remove(user)
                new_group.user_set.add(user)
            elif user == request.user:
                messages.error(request, self.MESSAGE_GROUP_NO_SELF_CHANGE)
            else:
                messages.error(request, self.MESSAGE_GROUP_NO_CHANGE_OWNER)

        except CustomUser.DoesNotExist:
            messages.error(request, self.MESSAGE_USER_NOT_FOUND)
        except Group.DoesNotExist:
            messages.error(request, self.MESSAGE_GROUP_NOT_FOUND)

        return self.redirect_to_view(request)

    def render_page(self, request, form, bulk_form):
        current_org = request.current_organization
        members = CustomUser.objects.filter(organizations=current_org).prefetch_related("groups")

        qs = UserInvitation.objects
        if not request.user.is_staff:
            qs = qs.filter(organization=current_org)

        invitations = qs.prefetch_related("organization", "role")

        return render(
            request,
            "mvp/settings/members.html",
            {
                "form": form,
                "bulk_form": bulk_form,
                "members": members,
                "num_members": len(members),
                "invitations": invitations,
                "roles": self.get_roles(),
            },
        )

    def send_invitation_mail(self, request, invitation):
        tool_name = settings.APP_NAME

        html_content = self.get_email_content(request, invitation, tool_name)
        plain_text_content = strip_tags(html_content)
        EmailService().send_email(
            subject=f"Your invitation to {tool_name}",
            message=plain_text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=html_content,
        )

    def get_email_content(self, request, invitation, tool_name):
        # TODO this is scrappy, proper would be to use `request.build_absolute_uri` and having apache forward like https://stackoverflow.com/a/68310760
        signup_url = f"{settings.SITE_DOMAIN}{reverse_lazy('signup')}"
        return render_to_string(
            "account/email/invitation.html",
            {
                "invitation": invitation,
                "sender": request.user,
                "organization": request.current_organization,
                "url": f"{signup_url}?invite={invitation.token}",
                "tool_name": tool_name,
            },
        )

    def get_roles(self):
        roles = {
            OrgRole.OWNER: {
                "label": "Owner",
                "description": "Full access to all sections and can manage members.",
            },
            # TODO disabled for now, might remove it later
            # OrgRole.SETTINGS_EDITOR: {
            #     "label": "Settings Editor",
            #     "description": "Access to settings.",
            # },
            # OrgRole.COMPLIANCE_LEADER: {
            #     "label": "Compliance Leader",
            #     "description": "Access to Compliance Standards and Settings",
            # },
            # OrgRole.ENGINEERING_LEADER: {
            #     "label": "Engineering Leader",
            #     "description": f"Access to {settings.APP_NAME} and Settings",
            # },
            # OrgRole.DEVELOPER: {
            #     "label": "Developer",
            #     "description": f"Access to {settings.APP_NAME}",
            # },
            OrgRole.USER: {
                "label": "User",
                "description": "Full access to all sections.",
            },
        }

        groups = Group.objects.filter(name__in=list(roles))
        for group in groups:
            if group.name in roles:
                roles[group.name]["id"] = group.pk

        return list(roles.values())

    # TODO: test
    def redirect_to_view(self, request, invites_section=False):
        url = reverse_lazy("users")
        if invites_section:
            url = f"{url}#{self.ANCHOR_PENDING_INVITES}"

        return redirect(url)

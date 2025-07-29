import posthog
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from compass.onboarding.serializers import InsightsNotificationsSerializer
from mvp.models import CustomUser
from mvp.services import EmailService


class BaseAssignSetupView(PermissionRequiredMixin, CreateAPIView):
    permission_required = None
    template_name = None
    connect_url = None
    email_subject = None

    def post(self, request, *args, **kwargs):
        assigned_user = get_object_or_404(
            CustomUser,
            email=request.data.get("email"),
            organization=request.current_organization,
        )
        html_content = self.get_email_content(
            assigned_user_first_name=assigned_user.first_name,
            requesting_user_full_name=request.user.get_full_name(),
            organization_name=request.current_organization.name,
            connect_url=self.connect_url,
        )
        plain_text_content = strip_tags(html_content)
        EmailService.send_email(
            subject=self.email_subject,
            message=plain_text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[assigned_user.email],
            html_message=html_content,
        )
        return Response({"success": True})

    def get_email_content(
        self,
        assigned_user_first_name,
        requesting_user_full_name,
        organization_name,
        connect_url,
    ):
        return render_to_string(
            self.template_name,
            {
                "assigned_user_first_name": assigned_user_first_name,
                "requesting_user_full_name": requesting_user_full_name,
                "organization_name": organization_name,
                "connect_url": connect_url,
            },
        )


class AssignGitSetupToColleagueView(BaseAssignSetupView):
    permission_required = "mvp.can_view_compass_assign_git_setup_to_colleague"
    template_name = "compass/onboarding/assign_git_setup_to_colleague_email.html"
    connect_url = f"{settings.SITE_DOMAIN}/compass/onboarding/connect-vcs"
    email_subject = f"Request to connect Version Control System to Sema {settings.APP_NAME}"


class AssignJiraSetupToColleagueView(BaseAssignSetupView):
    permission_required = "mvp.can_view_compass_assign_jira_setup_to_colleague"
    template_name = "compass/onboarding/assign_jira_setup_to_colleague_email.html"
    connect_url = f"{settings.SITE_DOMAIN}/compass/onboarding/connect-jira"
    email_subject = f"Request to connect Jira to Sema {settings.APP_NAME}"


class InsightsNotificationsView(CreateAPIView, RetrieveAPIView):
    permission_required = "mvp.can_set_compass_insights_notifications"
    serializer_class = InsightsNotificationsSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        data = {
            "anomaly_insights": user.compass_anomaly_insights_notifications,
            "summary_insights": user.compass_summary_insights_notifications,
        }
        serializer = self.serializer_class(data)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        user = request.user
        data = {
            "anomaly_insights": request.data.get("anomaly_insights"),
            "summary_insights": request.data.get("summary_insights"),
        }
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)

        user.compass_anomaly_insights_notifications = serializer.validated_data["anomaly_insights"]
        user.compass_summary_insights_notifications = serializer.validated_data["summary_insights"]
        user.save()
        return Response(serializer.data)


class CompleteOnboardingView(APIView):
    def post(self, request, *args, **kwargs):
        current_org = request.current_organization
        current_org.onboarding_completed = True
        current_org.save()

        posthog.capture(request.user.email, event="onboarding_complete")

        return Response({"success": True})

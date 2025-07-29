import json
import logging
import urllib.parse
import uuid

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from rest_framework.generics import RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from sentry_sdk import capture_message, push_scope

from compass.integrations.apis import BitBucketApi, GitHubApi
from compass.integrations.apis.jira_api import JiraApi, JiraApiConfig
from compass.integrations.integrations import JiraIntegration
from mvp.mixins import DecodePublicIdMixin
from mvp.models import CustomUser, DataProviderConnection, JiraProject
from mvp.serializers import JiraProjectSerializer
from mvp.services import ConnectedIntegrationsService


class ConnectGitProviderView(PermissionRequiredMixin, RetrieveAPIView):
    permission_required = "mvp.can_view_compass_integrations"

    def get(self, request, *args, **kwargs):
        organization = request.current_organization
        connection_data = {
            "azure_devops": {
                "url": reverse("connect_azure_devops"),
                "is_connected": ConnectedIntegrationsService.is_azure_devops_connected(organization),
            },
            "bitbucket": {
                "url": BitBucketApi.get_installation_url(settings.BITBUCKET_OAUTH_CONSUMER_KEY),
                "is_connected": ConnectedIntegrationsService.is_bitbucket_connected(organization),
            },
            "github": {
                "url": GitHubApi.get_installation_url(settings.GITHUB_APP_NAME, state="compass"),
                "is_connected": ConnectedIntegrationsService.is_github_connected(organization),
            },
        }
        return Response(connection_data)


# TODO move jira view classes to connect_jira_view
class ConnectJiraView(PermissionRequiredMixin, RetrieveAPIView):
    permission_required = "mvp.can_view_compass_integrations"

    def get(self, request, *args, **kwargs):
        organization = request.current_organization
        connection = self.get_or_create_connection(organization=organization, user=request.user)

        if not connection.data:
            # state_secret can be missing if we delete connection data to inactivate connection
            connection.data = {"state_secret": uuid.uuid4().hex}
            connection.save()

        projects = None
        if is_connected := JiraIntegration.is_connection_connected(connection):
            projects = JiraProject.objects.filter(organization=organization)

        is_onboarding = request.GET.get("is_onboarding", "false").lower() == "true"

        projects_serialized = JiraProjectSerializer(projects, many=True).data if projects else None
        state_data = {
            "secret": connection.data.get("state_secret"),
            "is_onboarding": is_onboarding,
        }
        state_param = urllib.parse.quote(json.dumps(state_data))

        connection_data = {
            "url": JiraApi.get_installation_url(state_param),
            "projects": projects_serialized,
            "is_connected": is_connected,
        }
        return Response(connection_data)

    @classmethod
    def get_or_create_connection(cls, organization, user):
        existing_connection = DataProviderConnection.objects.filter(
            provider=JiraIntegration().provider,
            organization=organization,
        ).first()

        if existing_connection:
            if "state_secret" not in existing_connection.data:
                existing_connection.data["state_secret"] = uuid.uuid4().hex
            existing_connection.data["initiating_user_id"] = user.id
            existing_connection.save()
            return existing_connection

        return DataProviderConnection.objects.create(
            provider=JiraIntegration().provider,
            organization=organization,
            data={"state_secret": uuid.uuid4().hex, "initiating_user_id": user.id},
        )


class ConnectJiraRedirectView(RetrieveAPIView):
    permission_classes = [AllowAny]
    settings_redirect_path = f"{settings.SITE_DOMAIN}/settings/connect/jira/"
    onboarding_redirect_path = f"{settings.SITE_DOMAIN}/onboarding/connect-jira/"
    error_message = "Connection failed. Please try again"

    def get(self, request, *args, **kwargs):
        state_param = request.GET.get("state")
        state_data = json.loads(urllib.parse.unquote(state_param))
        state_secret = state_data.get("secret")
        is_onboarding = state_data.get("is_onboarding", False)

        connection = self.get_connection(state_secret)

        redirect_path = self.onboarding_redirect_path if is_onboarding else self.settings_redirect_path

        if not connection:
            with push_scope() as scope:
                scope.set_extra("state_secret", self.obfuscate_state_secret(state_secret))
                capture_message(
                    "Jira connection not found with state_secret",
                    level="error",
                )

            path = f"{redirect_path}?status=error&message={self.error_message}"
            return redirect(path)

        auth_code = request.GET.get("code")
        response = JiraApi.get_access_and_refresh_tokens(auth_code)
        if not response.ok:
            with push_scope() as scope:
                scope.set_extra("response", response.json())
                capture_message(
                    "Error when fetching access/refresh tokens from Jira",
                    level="error",
                )
            path = f"{redirect_path}?status=error&message={self.error_message}"
            return redirect(path)

        response_data = response.json()
        connection_data = {
            "access_token": response_data.get("access_token"),
            "refresh_token": response_data.get("refresh_token"),
        }
        api_config = JiraApiConfig(**connection_data)
        api = JiraApi(api_config)
        resources = api.get_accessible_resources()
        if not resources:
            message = "Connection failed. You do not have access to any resources"
            path = f"{redirect_path}?status=error&message={message}"
            return redirect(path)

        # TODO: getting first cloud_id for now, need to handle multiple cloud_ids?
        cloud_id = resources[0]["id"]
        connection_data.update({"cloud_id": cloud_id})
        connection.data.update(connection_data)

        # Note: If the connection is completed but the `initiating_user_id` in `data`
        # does not match `connected_by`, it likely means the initiating user did not
        # finish the connection flow.
        initiating_user_id = connection.data.pop("initiating_user_id", None)
        try:
            initiating_user = CustomUser.objects.get(id=initiating_user_id)
        except CustomUser.DoesNotExist:
            logging.exception(
                "Could not determine user initiating Jira connection",
                extra={
                    "jira_data_provider_connection_id": connection.id,
                    "initiating_user_id": initiating_user_id,
                },
            )
            initiating_user = None

        connection.connected_by = initiating_user
        connection.connected_at = timezone.now()
        connection.save()

        JiraIntegration().fetch_data(connection)

        message = "Jira connected!"
        path = f"{redirect_path}?status=success&message={message}"
        return redirect(path)

    def obfuscate_state_secret(self, state_secret):
        """
        Obfuscates state_secret for logging purposes.
        """
        if not state_secret:
            return None
        return f"{state_secret[:4]}{'*' * (len(state_secret) - 4)}"

    @classmethod
    def get_connection(cls, state_secret):
        return DataProviderConnection.objects.filter(
            data__state_secret=state_secret,
            provider=JiraIntegration().provider,
        ).first()


class UpdateJiraProjectSelectionView(PermissionRequiredMixin, DecodePublicIdMixin, UpdateAPIView):
    permission_required = "mvp.can_view_compass_integrations"

    def put(self, request, project_public_id, *args, **kwargs):
        organization = request.current_organization
        is_selected = request.data.get("is_selected", False)
        project_id = self.decode_id(project_public_id)

        project = get_object_or_404(JiraProject, organization=organization, id=project_id)
        project.is_selected = is_selected
        if not project.is_selected:
            # remove project from all groups
            project.repository_group.clear()

        project.save()

        return Response({"status": "success", "is_selected": is_selected})

from django.urls import path

from compass.integrations.views import (
    ConnectGitProviderView,
    ConnectJiraRedirectView,
    ConnectJiraView,
    UpdateJiraProjectSelectionView,
)

urlpatterns = [
    path(
        "connect-git-provider/",
        ConnectGitProviderView.as_view(),
        name="compass_api_integrations_connect_git_provider",
    ),
    path(
        "connect-jira/",
        ConnectJiraView.as_view(),
        name="compass_api_integrations_connect_jira",
    ),
    path(
        "connect-jira-redirect/",
        ConnectJiraRedirectView.as_view(),
        name="compass_api_integrations_connect_jira_redirect",
    ),
    path(
        "connect-jira/projects/<str:project_public_id>/selection/",
        UpdateJiraProjectSelectionView.as_view(),
        name="compass_api_integrations_update_jira_project_selection",
    ),
]

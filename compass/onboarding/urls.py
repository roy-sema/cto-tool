from django.urls import path

from compass.onboarding.views import (
    AssignGitSetupToColleagueView,
    AssignJiraSetupToColleagueView,
    CompleteOnboardingView,
    InsightsNotificationsView,
)

urlpatterns = [
    path(
        "assign-git-setup-to-colleague/",
        AssignGitSetupToColleagueView.as_view(),
        name="compass_api_assign_git_setup_to_colleague",
    ),
    path(
        "assign-jira-setup-to-colleague/",
        AssignJiraSetupToColleagueView.as_view(),
        name="compass_api_assign_jira_setup_to_colleague",
    ),
    path(
        "complete/",
        CompleteOnboardingView.as_view(),
        name="compass_api_complete_onboarding",
    ),
    path(
        "insights-notifications/",
        InsightsNotificationsView.as_view(),
        name="compass_api_insights_notifications",
    ),
]

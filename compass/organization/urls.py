from django.urls import path

from compass.organization.views import (
    OrganizationDeveloperGroupsView,
    OrganizationRepositoryGroupsView,
    OrganizationUsersView,
)

urlpatterns = [
    path(
        "developer-groups/",
        OrganizationDeveloperGroupsView.as_view(),
        name="compass_api_organization_developer_groups",
    ),
    path(
        "repository-groups/",
        OrganizationRepositoryGroupsView.as_view(),
        name="compass_api_organization_repository_groups",
    ),
    path(
        "users/",
        OrganizationUsersView.as_view(),
        name="compass_api_organization_users",
    ),
]

from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect, reverse
from django.urls import include, path, re_path

from compass.documents.views import DocumentsSettingsView
from mvp.views import (
    ChangeOrganizationView,
    ComplianceStandardsView,
    ConnectAzureDevOpsView,
    ConnectBitBucketView,
    ConnectCodacyView,
    ConnectGitHubView,
    ConnectionsView,
    ConnectIRadarView,
    ConnectJiraView,
    ConnectMSTeamsView,
    ConnectSnykView,
    ContactView,
    DailyMessageView,
    DashboardView,
    DeveloperEditView,
    DeveloperGroupEditView,
    DeveloperGroupsDashboardView,
    DeveloperGroupsExportView,
    ExportGBOMView,
    HomeView,
    InitiativesView,
    OtherSettingsView,
    PullRequestScanView,
    RawContextualization,
    RepositoryDetailView,
    RepositoryGroupEditView,
    RepositoryGroupsDashboardView,
    RepositoryGroupsView,
    RequestAccessView,
    RuleEditView,
    SettingsView,
    SignUpView,
    UsersView,
)

REDIRECT_MAP = {
    HomeView: "home",
    SettingsView: "settings",
}


def redirect_to_main(request):
    user = request.user
    if user.is_authenticated and not user.is_superuser:
        for _class, path_name in REDIRECT_MAP.items():
            if user.has_perm(_class.permission_required):
                return redirect(reverse(path_name))

    return redirect(reverse("home"))


allauth_disabled_routes = [
    "accounts/2fa/recovery-codes/generate/",
    "accounts/2fa/totp/deactivate/",
    "accounts/confirm-email/",
    "accounts/confirm-email/<key>/",
    "accounts/email/",
    "accounts/login/code/confirm/",
    "accounts/password/change/",
    "accounts/password/set/",
]

urlpatterns = [
    path("", redirect_to_main, name="root_redirect"),
    # Vue routes
    path("home/", HomeView.as_view(), name="home"),
    path("profile/", HomeView.as_view(), name="profile"),
    re_path(r"^coming-soon/.*$", HomeView.as_view(), name="coming_soon"),
    re_path(r"^engineering-radar/.*$", HomeView.as_view(), name="engineering_radar"),
    re_path(r"^onboarding/.*$", HomeView.as_view(), name="onboarding"),
    re_path(r"^product-roadmap-radar/.*$", HomeView.as_view(), name="product_roadmap_radar"),
    # Django routes
    *[path(route, lambda request: redirect("account_login")) for route in allauth_disabled_routes],
    path("accounts/signup/", lambda request: redirect("signup"), name="account_signup"),
    path("accounts/", include("allauth.urls")),
    path("genai-radar/", lambda request: redirect("dashboard"), name="genai_radar"),
    path("genai-radar/dashboard", DashboardView.as_view(), name="dashboard"),
    path(
        "genai-radar/repository-groups/",
        RepositoryGroupsDashboardView.as_view(),
        name="repository_groups_dashboard",
    ),
    path(
        "genai-radar/developer-groups/",
        DeveloperGroupsDashboardView.as_view(),
        name="developer_groups_dashboard",
    ),
    path(
        "genai-radar/developer-groups/export/",
        DeveloperGroupsExportView.as_view(),
        name="export_developer_groups",
    ),
    path(
        "genai-radar/export-gbom/",
        ExportGBOMView.as_view(),
        name="export_gbom",
    ),
    path(
        "genai-radar/pulls/<str:external_id>/<int:pr_number>/",
        PullRequestScanView.as_view(),
        name="pull_request_scan",
    ),
    path(
        "genai-radar/repositories/<str:pk_encoded>/",
        RepositoryDetailView.as_view(),
        name="repository_detail",
    ),
    path(
        "change-organization/",
        ChangeOrganizationView.as_view(),
        name="change_organization",
    ),
    path(
        "compliance-standards/",
        ComplianceStandardsView.as_view(),
        name="compliance_standards",
    ),
    path("contact/", ContactView.as_view(), name="contact"),
    path("hijack/", include("hijack.urls")),
    path("request-access/", RequestAccessView.as_view(), name="request_access"),
    path("settings/", SettingsView.as_view(), name="settings"),
    path("settings/other/", OtherSettingsView.as_view(), name="other_settings"),
    path("settings/connections/", ConnectionsView.as_view(), name="connections"),
    path(
        "settings/connect/azure_devops/",
        ConnectAzureDevOpsView.as_view(),
        name="connect_azure_devops",
    ),
    path(
        "settings/connect/bitbucket/",
        ConnectBitBucketView.as_view(),
        name="connect_bitbucket",
    ),
    path("settings/connect/codacy/", ConnectCodacyView.as_view(), name="connect_codacy"),
    path("settings/connect/github/", ConnectGitHubView.as_view(), name="connect_github"),
    path("settings/connect/iradar/", ConnectIRadarView.as_view(), name="connect_iradar"),
    path("settings/connect/snyk/", ConnectSnykView.as_view(), name="connect_snyk"),
    path("settings/connect/jira/", ConnectJiraView.as_view(), name="connect_jira"),
    path("settings/connect-ms-teams/", ConnectMSTeamsView.as_view(), name="connect_ms_teams"),
    path(
        "settings/other/developer-groups/<str:pk_encoded>/",
        DeveloperGroupEditView.as_view(),
        name="developer_group_edit",
    ),
    path(
        "settings/other/developers/<str:pk_encoded>/",
        DeveloperEditView.as_view(),
        name="developer_edit",
    ),
    path("settings/users/", UsersView.as_view(), name="users"),
    path(
        "settings/repository-groups/",
        RepositoryGroupsView.as_view(),
        name="repository_groups",
    ),
    path(
        "settings/repository-groups/<str:pk_encoded>/",
        RepositoryGroupEditView.as_view(),
        name="repository_group_edit",
    ),
    path("settings/other/rules/<str:pk_encoded>/", RuleEditView.as_view(), name="rule_edit"),
    path("settings/daily-message/", DailyMessageView.as_view(), name="daily_message"),
    path(
        "settings/documents/",
        DocumentsSettingsView.as_view(),
        name="documents",
    ),
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "contextualization/data/",
        RawContextualization.as_view(),
        name="contextualization_data",
    ),
    # legacy routes
    path("join-list/", lambda request: redirect("request_access"), name="join_list"),
    # Redirect legacy URLs to new ones
    re_path(
        r"^pulls/(.*)$",
        lambda request, path: redirect("/genai-radar/pulls/" + path, permanent=True),
    ),
    path(
        "settings/initiatives/",
        InitiativesView.as_view(),
        name="initiatives",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

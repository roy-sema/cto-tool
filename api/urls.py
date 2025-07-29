from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (
    AttestationViewSet,
    CurrentUserView,
    DeveloperGroupView,
    DeveloperView,
    GenAIFeedbackViewSet,
    OrganizationMetricsView,
    PullRequestCompositionView,
    PullRequestReRunAnalysisView,
    RepositoriesCompositionView,
    RepositoryFileViewSet,
    VersionView,
    WebhookAzureDevOpsView,
    WebhookBitBucketView,
    WebhookGitHubView,
)
from api.views.repository_group_list_view import RepositoryGroupView

router = DefaultRouter()
router.register(r"genaifeedback", GenAIFeedbackViewSet, basename="genaifeedback-api")
router.register(
    r"repositories/(?P<pk_encoded>[^/]+)/attestation",
    AttestationViewSet,
    basename="attestation",
    # NOTE: includes custom action:
    # - repositories/<pk_encoded>/attestation/agree-all/
)
router.register(
    r"repositories/(?P<pk_encoded>[^/.]+)/commits/(?P<sha>[^/.]+)/files",
    RepositoryFileViewSet,
    basename="repositoryfile",
)

urlpatterns = [
    path(
        "organization/metrics/",
        OrganizationMetricsView.as_view(),
        name="organization_metrics",
    ),
    path(
        "repositories/groups/",
        RepositoryGroupView.as_view(),
        name="repository_group_list",
    ),
    path(
        "repositories/composition/",
        RepositoriesCompositionView.as_view(),
        name="repositories_composition",
    ),
    path(
        "repositories/<str:pk_encoded>/pulls/<int:pr_number>/composition/",
        PullRequestCompositionView.as_view(),
        name="pull_request_composition",
    ),
    path(
        "repositories/<str:pk_encoded>/pulls/<int:pr_number>/re-run-analysis/",
        PullRequestReRunAnalysisView.as_view(),
        name="pull_request_re_run_analysis",
    ),
    path(
        "developers/groups/",
        DeveloperGroupView.as_view(),
        name="developer_group_list",
    ),
    path(
        "developers/groups/<str:public_id>/developers/",
        DeveloperView.as_view(),
        name="developer_list",
    ),
    path("me/", CurrentUserView.as_view()),
    path("version/", VersionView.as_view()),
    path(
        "webhook-azure-devops/",
        WebhookAzureDevOpsView.as_view(),
        name="webhook-azure-devops",
    ),
    path("webhook-github/", WebhookGitHubView.as_view(), name="webhook-github"),
    path(
        "webhook-bitbucket/",
        WebhookBitBucketView.as_view(),
        name="webhook-bitbucket",
    ),
    path("", include(router.urls)),
]

from django.urls import include, path

urlpatterns = [
    path(
        "api/v1/",
        include(
            [
                path("budget/", include("compass.budget.urls")),
                path("codebase-reports/", include("compass.codebasereports.urls")),
                path("compliance/", include("compass.compliance.urls")),
                path("dashboard/", include("compass.dashboard.urls")),
                path("documents/", include("compass.documents.urls")),
                path("integrations/", include("compass.integrations.urls")),
                path("onboarding/", include("compass.onboarding.urls")),
                path("organization/", include("compass.organization.urls")),
                path("projects/", include("compass.projects.urls")),
                path("roadmap/", include("compass.roadmap.urls")),
                path("team-health/", include("compass.team.urls")),
                path("contextualization/", include("compass.contextualization.urls")),
            ]
        ),
    ),
]

from django.urls import include, path

from compass.projects.views import (
    ChatInputView,
    ChatResetView,
    ChatResultView,
    ChatRollbackView,
    ProjectsView,
)

chat_urlpatterns = [
    path("input/", ChatInputView.as_view(), name="compass_api_projects_chat_input"),
    path("result/", ChatResultView.as_view(), name="compass_api_projects_chat_result"),
    path(
        "rollback/",
        ChatRollbackView.as_view(),
        name="compass_api_projects_chat_rollback",
    ),
    path("reset/", ChatResetView.as_view(), name="compass_api_projects_chat_reset"),
]

urlpatterns = [
    path("chat/", include(chat_urlpatterns)),
    path("", ProjectsView.as_view(), name="compass_api_projects"),
]

from datetime import datetime, timedelta

from django.contrib.auth.mixins import PermissionRequiredMixin
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from compass.projects.models import ChatHistoryStatusChoices
from compass.projects.serializers import ChatHistorySerializer
from compass.projects.services import ChatService
from mvp.services import ContextualizationService
from mvp.utils import start_new_thread


class ProjectsView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_view_compass_projects"

    def get(self, request, *args, **kwargs):
        organization = request.current_organization

        active_chat, _ = ChatService.get_active_chat(organization)
        data, end_date = ChatService.read_projects_file(organization)
        if active_chat:
            projects = active_chat.result.get("changes", [])
            updated_at = active_chat.updated_at.timestamp()
        else:
            projects = data[0].get("changes", []) if data else []
            updated_at = end_date

        start_date = (
            datetime.fromtimestamp(end_date) - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value)
        ).timestamp()

        return Response(
            {
                "projects": projects,
                "updated_at": int(updated_at),
                "date_range": [int(start_date), int(end_date)] if end_date else None,
            }
        )


class ChatInputView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_make_compass_projects_chat_input"

    def post(self, request, *args, **kwargs):
        chat_input = request.data.get("chat_input")
        if not chat_input:
            return Response(
                {"error": "'chat_input' is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.process_input_chat_background(
            organization=request.current_organization,
            user=request.user,
            chat_input=chat_input,
        )
        return Response({"success": True})

    @start_new_thread
    def process_input_chat_background(self, organization, user, chat_input):
        ChatService.process_chat_input(
            organization=organization,
            user=user,
            chat_input=chat_input,
        )


class ChatResultView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_make_compass_projects_chat_input"
    serializer_class = ChatHistorySerializer

    def get(self, request, *args, **kwargs):
        active_chat, activated_from_error = ChatService.get_active_chat(
            organization=request.current_organization,
        )
        if activated_from_error:
            return Response(
                {"result": {}, "status": ChatHistoryStatusChoices.ERROR},
            )

        if not active_chat:
            # Returning status 'complete' so frontend
            # doesn't poll this endpoint unnecessarily
            return Response(
                {"result": {}, "status": ChatHistoryStatusChoices.COMPLETE},
            )

        serializer = self.serializer_class(active_chat)
        return Response(serializer.data)


class ChatResetView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_make_compass_projects_chat_input"
    serializer_class = ChatHistorySerializer

    def post(self, request, *args, **kwargs):
        operation = request.data.get("operation")
        if operation != "reset":
            return Response(
                {"error": "'operation' is not valid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chat = ChatService.reset_chat(request.current_organization, request.user)
        serializer = self.serializer_class(chat)
        return Response(serializer.data)


class ChatRollbackView(PermissionRequiredMixin, APIView):
    permission_required = "mvp.can_make_compass_projects_chat_input"
    serializer_class = ChatHistorySerializer

    def post(self, request, *args, **kwargs):
        operation = request.data.get("operation")
        if operation != "rollback":
            return Response(
                {"error": "'operation' is not valid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chat = ChatService.rollback_chat(request.current_organization, request.user)
        serializer = self.serializer_class(chat)
        return Response(serializer.data)

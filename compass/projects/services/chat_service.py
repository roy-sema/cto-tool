from sentry_sdk import capture_exception, capture_message, push_scope

from compass.projects.models import ChatHistory, ChatHistoryStatusChoices
from mvp.models import CustomUser, Organization
from mvp.services import ContextualizationService
from mvp.utils import traceback_on_debug


class ChatService(ContextualizationService):
    @classmethod
    def get_active_chat(cls, organization: Organization) -> tuple[ChatHistory | None, bool]:
        """
        Get the active chat for the given organization.

        If the active chat has status ERROR, this method will deactivate
        it and return the activated rollback chat if it exists.
        A boolean indicting that the active chat was activated from
        an error rollback is also returned.
        """
        chat = ChatHistory.objects.filter(
            organization=organization,
            is_active=True,
        ).first()
        if not chat:
            return None, False

        if chat.status == ChatHistoryStatusChoices.ERROR:
            chat.is_active = False
            chat.save()
            new_active_chat = chat.rollback_chat
            if new_active_chat:
                new_active_chat.is_active = True
                new_active_chat.save()
                return new_active_chat, True
            else:
                return None, True

        return chat, False

    @classmethod
    def deactivate_active_chat(cls, organization: Organization) -> ChatHistory | None:
        active_chat, _ = cls.get_active_chat(organization)
        if active_chat:
            active_chat.is_active = False
            active_chat.save()
            return active_chat

        return None

    @classmethod
    def process_chat_input(cls, organization: Organization, user: CustomUser, chat_input: str) -> ChatHistory | bool:
        last_active_chat = cls.deactivate_active_chat(organization)

        chat = ChatHistory.objects.create(
            organization=organization,
            created_by=user,
            prompt=chat_input,
            status=ChatHistoryStatusChoices.PENDING,
            rollback_chat=last_active_chat,
            is_active=True,
        )

        _, existing_result_timestamp = cls.read_chat_result(organization)

        try:
            cls.process_project_information_chat_input(organization)
        except Exception as error:
            with push_scope() as scope:
                scope.set_extra("organization_id", organization.id)
                scope.set_extra("chat_input", chat_input)
                capture_exception(error)
                traceback_on_debug()

            chat.status = ChatHistoryStatusChoices.ERROR
            chat.save()
            return False

        result, new_result_timestamp = cls.read_chat_result(organization)
        if new_result_timestamp == existing_result_timestamp:
            capture_message(
                f"Chat result timestamp did not change for {organization.name}",
                level="error",
            )
            chat.status = ChatHistoryStatusChoices.ERROR
            chat.save()
            return False

        chat.status = ChatHistoryStatusChoices.COMPLETE
        chat.result = result
        chat.save()
        return chat

    @classmethod
    def read_projects_file(cls, organization: Organization) -> tuple[dict, float]:
        return cls.load_output_data(
            organization,
            cls.OUTPUT_FILENAME_PROJECTS,
        )

    @classmethod
    def read_chat_result(cls, organization: Organization) -> tuple[dict, float]:
        script_output_path = cls.get_script_output_path(
            data_dir=cls.get_contextualization_directory(organization),
            suffix=cls.SCRIPT_OUTPUT_SUFFIX_GIT_INITIATIVES_COMBINED,
        )
        return cls.load_output_data(organization, script_output_path)

    @classmethod
    def reset_chat(cls, organization: Organization, user: CustomUser) -> ChatHistory:
        cls.deactivate_active_chat(organization)

        data, _ = cls.read_projects_file(organization)
        result = data[0]

        return ChatHistory.objects.create(
            organization=organization,
            created_by=user,
            status=ChatHistoryStatusChoices.COMPLETE,
            result=result,
            is_reset=True,
            is_active=True,
        )

    @classmethod
    def rollback_chat(cls, organization: Organization, user: CustomUser) -> ChatHistory:
        last_active_chat = cls.deactivate_active_chat(organization)

        if last_active_chat and last_active_chat.rollback_chat:
            result = last_active_chat.rollback_chat.result
            prompt = last_active_chat.rollback_chat.prompt
            rollback_chat = last_active_chat.rollback_chat.rollback_chat
        else:
            # If there is no rollback chat, load initial data
            data, _ = cls.read_projects_file(organization)
            result = data[0]
            prompt = None
            rollback_chat = None

        return ChatHistory.objects.create(
            organization=organization,
            created_by=user,
            status=ChatHistoryStatusChoices.COMPLETE,
            prompt=prompt,
            rollback_chat=rollback_chat,
            result=result,
            is_rollback=True,
            is_active=True,
        )

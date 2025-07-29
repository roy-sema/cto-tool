from django.test import TestCase

from compass.projects.models import ChatHistory, ChatHistoryStatusChoices
from compass.projects.services import ChatService
from mvp.models import CustomUser, Organization


class TestChatService(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Test Org")
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            password="Pa$$worD",
        )

    def create_chat_history(self):
        chat_1 = ChatHistory.objects.create(
            organization=self.organization,
            created_by=self.user,
            prompt="Rename “UI/Frontend Improvements” to “Frontend”",
            status=ChatHistoryStatusChoices.COMPLETE,
            result={
                "changes": [
                    {
                        "name": "Frontend",
                        "percentage": 43.48,
                        "justification": "none",
                    },
                ],
                "summary": "",
            },
        )
        chat_2 = ChatHistory.objects.create(
            organization=self.organization,
            created_by=self.user,
            prompt="Rename “Frontend” to “Frontend 1”",
            status=ChatHistoryStatusChoices.COMPLETE,
            rollback_chat=chat_1,
            result={
                "changes": [
                    {
                        "name": "Frontend 1",
                        "percentage": 4.35,
                        "justification": "none",
                    },
                ],
                "summary": "none",
            },
        )
        chat_3 = ChatHistory.objects.create(
            organization=self.organization,
            created_by=self.user,
            prompt="Rename “Frontend 1” to “Frontend 2”",
            status=ChatHistoryStatusChoices.COMPLETE,
            rollback_chat=chat_2,
            result={
                "changes": [
                    {
                        "name": "Frontend 2",
                        "percentage": 4.35,
                        "justification": "none",
                    },
                ],
                "summary": "none",
            },
            is_active=True,
        )
        return chat_1, chat_2, chat_3

    def test_rollback(self):
        chat_1, chat_2, chat_3 = self.create_chat_history()
        ChatService.rollback_chat(self.organization, self.user)
        chat_1.refresh_from_db()
        chat_2.refresh_from_db()
        chat_3.refresh_from_db()

        chats = ChatHistory.objects.filter(organization=self.organization).order_by("created_at")

        self.assertEqual(chats.count(), 4)
        self.assertFalse(chat_1.is_active)
        self.assertFalse(chat_2.is_active)
        self.assertFalse(chat_3.is_active)

        chat = chats.last()
        self.assertTrue(chat.is_active)
        self.assertTrue(chat.is_rollback)
        self.assertEqual(chat.rollback_chat, chat_1)
        self.assertEqual(chat.prompt, chat_2.prompt)

        # Rollback again
        ChatService.rollback_chat(self.organization, self.user)
        chat_1.refresh_from_db()
        chat_2.refresh_from_db()
        chat_3.refresh_from_db()

        chats = ChatHistory.objects.filter(organization=self.organization).order_by("created_at")

        self.assertEqual(chats.count(), 5)
        self.assertFalse(chat_1.is_active)
        self.assertFalse(chat_2.is_active)
        self.assertFalse(chat_3.is_active)

        chat = chats.last()
        self.assertTrue(chat.is_active)
        self.assertIsNone(chat.rollback_chat)
        self.assertEqual(chat.prompt, chat_1.prompt)

    def test_complex_rollback(self):
        # Tests rollback logic when a user prompts after a rollback
        chat_1, _, _ = self.create_chat_history()
        ChatService.rollback_chat(self.organization, self.user)

        # Rollback again
        ChatService.rollback_chat(self.organization, self.user)
        chats = ChatHistory.objects.filter(organization=self.organization).order_by("created_at")
        self.assertEqual(chats.count(), 5)
        last_active_chat, _ = ChatService.get_active_chat(self.organization)
        self.assertTrue(last_active_chat.result, chat_1.result)

        # Simulate new user prompt after rollback
        chat = ChatHistory.objects.create(
            organization=self.organization,
            created_by=self.user,
            prompt="Rename “Frontend” to “Fred's Frontend”",
            rollback_chat=ChatService.deactivate_active_chat(self.organization),
            result={
                "changes": [
                    {
                        "name": "Fred's Frontend",
                        "percentage": 4.35,
                        "justification": "none",
                    },
                ],
                "summary": "none",
            },
            is_active=True,
        )
        active_chat, _ = ChatService.get_active_chat(self.organization)
        self.assertEqual(chat, active_chat)

        # Rollback third time
        ChatService.rollback_chat(self.organization, self.user)
        chat.refresh_from_db()
        self.assertFalse(chat.is_active)
        active_chat, _ = ChatService.get_active_chat(self.organization)
        self.assertEqual(active_chat.prompt, last_active_chat.prompt)
        self.assertEqual(active_chat.result, last_active_chat.result)

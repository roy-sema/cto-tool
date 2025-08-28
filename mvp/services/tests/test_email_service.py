from unittest.mock import ANY, Mock, patch

from django.test import TestCase, override_settings

from mvp.services.email_service import EmailService
from mvp.tests.factories import CustomUserFactory, OrganizationFactory


class EmailMock:
    def __init__(
        self,
        subject="",
        body="",
        from_email=None,
        to=None,
        bcc=None,
        connection=None,
        attachments=None,
        headers=None,
        alternatives=None,
        cc=None,
        reply_to=None,
    ):
        self.subject = subject
        self.body = body
        self.from_email = from_email
        self.to = to
        self.bcc = bcc
        self.connection = connection
        self.attachments = attachments
        self.headers = headers
        self.alternatives = alternatives or []
        self.cc = cc
        self.reply_to = reply_to

    def attach_alternative(self, content, mimetype):
        self.alternatives.append((content, mimetype))

    def __eq__(self, value):
        if not (isinstance(value, EmailMock)):
            return False
        props = (
            "subject",
            "body",
            "from_email",
            "to",
            "bcc",
            "connection",
            "attachments",
            "headers",
            "alternatives",
            "cc",
            "reply_to",
        )
        return all(getattr(self, prop) == getattr(value, prop) for prop in props)


class EmailServiceTestCase(TestCase):
    @patch("mvp.services.email_service.EmailMultiAlternatives", new_callable=lambda: EmailMock)
    @patch("mvp.services.email_service.get_connection")
    def test_send_email(self, get_connection_mock, *args, **kwargs):
        mock_connection = Mock()
        mock_connection.send_messages.return_value = 1
        get_connection_mock.return_value = mock_connection
        with self.subTest("should call return true if email is sent"):
            subject = "somebody once"
            message = "told me"
            from_email = "test@example.com"
            recipient_list = ["recipient@example.com"]
            email_service = EmailService(fail_silently=True, auth_user="test_user", auth_password="test_pass")
            result = email_service.send_email(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
            )
            self.assertEqual(result, True)
            get_connection_mock.assert_called_once_with(
                username="test_user",
                password="test_pass",
                fail_silently=True,
            )
            messages = [
                EmailMock(
                    subject=subject,
                    body=message,
                    from_email=from_email,
                    to=recipient_list,
                ),
            ]
            mock_connection.send_messages.assert_called_with(messages)
        get_connection_mock.reset_mock()
        with self.subTest("should reuse connection for multiple sequential emails"):
            email_service = EmailService()
            email_service.send_email(
                subject="somebody once",
                message="told me",
                from_email="test@example.com",
                recipient_list=["recipient@example.com"],
            )
            email_service.send_email(
                subject="the world",
                message="is gonna roll me",
                from_email="test@example.com",
                recipient_list=["recipient@example.com"],
            )
            get_connection_mock.assert_called_once()
        get_connection_mock.reset_mock()
        get_connection_mock.return_value = 0
        with self.subTest("should return false if send_email returns 0"):
            email_service = EmailService()
            result = email_service.send_email(
                subject="Test Subject",
                message="Test message",
                from_email="test@example.com",
                recipient_list=["recipient@example.com"],
            )
            self.assertFalse(result)
            get_connection_mock.assert_called_once()
        get_connection_mock.reset_mock()
        get_connection_mock.side_effect = Exception("Test connection error")
        with self.subTest("should return false if sending email fails"):
            email_service = EmailService()
            result = email_service.send_email(
                subject="Test Subject",
                message="Test message",
                from_email="test@example.com",
                recipient_list=["recipient@example.com"],
            )
            self.assertFalse(result)
            get_connection_mock.assert_called_once()

    @override_settings(
        SEND_ANALYSIS_STARTED_EMAIL_ACTIVE=True,
        ANALYSIS_COMPLETE_EMAIL="admin@test.com",
        SITE_DOMAIN="https://example.com",
        APP_NAME="Test App",
        DEFAULT_FROM_EMAIL="noreply@test.com",
    )
    @patch("mvp.services.email_service.EmailMultiAlternatives", new_callable=lambda: EmailMock)
    @patch("mvp.services.email_service.get_connection")
    def test_send_analysis_started_email(self, get_connection_mock, *args, **kwargs):
        mock_connection = Mock()
        mock_connection.send_messages.return_value = 2
        get_connection_mock.return_value = mock_connection
        user = CustomUserFactory()
        with override_settings(ANALYSIS_COMPLETE_EMAIL=None):
            with self.subTest("should return false when no email addresses available"):
                organization = OrganizationFactory(connection_issued_by=None)
                email_service = EmailService()
                result = email_service.send_analysis_started_email(organization)
                self.assertFalse(result)
            with self.subTest("should send email when conditions are met"):
                organization = OrganizationFactory(connection_issued_by=user)
                email_service = EmailService()
                result = email_service.send_analysis_started_email(organization)
                self.assertTrue(result)
                mock_connection.send_messages.assert_called_with(
                    [
                        EmailMock(
                            subject="Test App Started Processing",
                            body=ANY,
                            alternatives=[(ANY, "text/html")],
                            from_email="noreply@test.com",
                            to=[user.email],
                        ),
                    ]
                )
        with self.subTest("should resend email to ANALYSIS_COMPLETE_EMAIL if set"):
            organization = OrganizationFactory(connection_issued_by=user)
            email_service = EmailService()
            result = email_service.send_analysis_started_email(organization)
            self.assertTrue(result)
            mock_connection.send_messages.assert_called_with(
                [
                    EmailMock(
                        subject="Test App Started Processing",
                        body=ANY,
                        alternatives=[(ANY, "text/html")],
                        from_email="noreply@test.com",
                        to=[user.email],
                    ),
                    EmailMock(
                        subject="Test App Started Processing",
                        body=ANY,
                        alternatives=[(ANY, "text/html")],
                        from_email="noreply@test.com",
                        to=["admin@test.com"],
                    ),
                ]
            )
        with self.subTest("should return false when no emails delivered"):
            mock_connection.send_messages.return_value = 0
            organization = OrganizationFactory(connection_issued_by=user)
            email_service = EmailService()
            result = email_service.send_analysis_started_email(organization)
            self.assertFalse(result)

    @override_settings(
        SEND_IMPORT_DONE_EMAIL_ACTIVE=True,
        ANALYSIS_COMPLETE_EMAIL="admin@test.com",
        SITE_DOMAIN="https://example.com",
        APP_NAME="Test App",
        DEFAULT_FROM_EMAIL="noreply@test.com",
    )
    @patch("mvp.services.email_service.EmailMultiAlternatives", new_callable=lambda: EmailMock)
    @patch("mvp.services.email_service.get_connection")
    def test_send_import_done_email(self, get_connection_mock, *args, **kwargs):
        mock_connection = Mock()
        mock_connection.send_messages.return_value = 2
        get_connection_mock.return_value = mock_connection
        user = CustomUserFactory()
        with override_settings(ANALYSIS_COMPLETE_EMAIL=None):
            with self.subTest("should return false when no email addresses available"):
                organization = OrganizationFactory(connection_issued_by=None)
                email_service = EmailService()
                result = email_service.send_import_done_email(organization)
                self.assertFalse(result)
            with self.subTest("should send email when conditions are met"):
                organization = OrganizationFactory(connection_issued_by=user)
                email_service = EmailService()
                result = email_service.send_import_done_email(organization)
                self.assertTrue(result)
                mock_connection.send_messages.assert_called_with(
                    [
                        EmailMock(
                            subject="Test App Finished Processing",
                            body=ANY,
                            alternatives=[(ANY, "text/html")],
                            from_email="noreply@test.com",
                            to=[user.email],
                        ),
                    ]
                )
        with self.subTest("should resend email to ANALYSIS_COMPLETE_EMAIL if set"):
            organization = OrganizationFactory(connection_issued_by=user)
            email_service = EmailService()
            result = email_service.send_import_done_email(organization)
            self.assertTrue(result)
            mock_connection.send_messages.assert_called_with(
                [
                    EmailMock(
                        subject="Test App Finished Processing",
                        body=ANY,
                        alternatives=[(ANY, "text/html")],
                        from_email="noreply@test.com",
                        to=[user.email],
                    ),
                    EmailMock(
                        subject="Test App Finished Processing",
                        body=ANY,
                        alternatives=[(ANY, "text/html")],
                        from_email="noreply@test.com",
                        to=["admin@test.com"],
                    ),
                ]
            )
        with self.subTest("should return false when no emails delivered"):
            mock_connection.send_messages.return_value = 0
            organization = OrganizationFactory(connection_issued_by=user)
            email_service = EmailService()
            result = email_service.send_import_done_email(organization)
            self.assertFalse(result)

import json
import logging
from typing import Any

from django.core.mail import EmailMultiAlternatives, get_connection, send_mass_mail
from django.template.loader import render_to_string
from django.urls import reverse
from sentry_sdk import capture_exception, push_scope

from cto_tool import settings
from mvp.utils import traceback_on_debug

logger = logging.getLogger(__name__)


class EmailService:
    # TODO refactor this to reduce code duplication

    @staticmethod
    def send_mass_html_mail(
        datatuple,
        fail_silently=False,
        auth_user=None,
        auth_password=None,
        connection=None,
        headers: dict[str, Any] | None = None,
    ) -> int:
        """
        based on django.core.mail.send_mass_mail

        Given a data_tuple of (subject, message, html_message, from_email,
        recipient_list), sends each message to each recipient list. Returns the
        number of emails sent.

        If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
        If auth_user and auth_password are set, they're used to log in.
        If auth_user is None, the EMAIL_HOST_USER setting is used.
        If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

        """
        connection = connection or get_connection(
            username=auth_user, password=auth_password, fail_silently=fail_silently
        )
        messages = []
        for subject, message, message_html, sender, recipient in datatuple:
            message = EmailMultiAlternatives(subject, message, sender, recipient, headers=headers)
            if message_html:
                message.attach_alternative(message_html, "text/html")
            messages.append(message)

        return connection.send_messages(messages)

    @staticmethod
    def _send_emails(
        subject,
        from_email,
        recipient_message_tuples,
        auth_user=None,
        auth_password=None,
        connection=None,
        headers: dict[str, Any] | None = None,
    ):
        if not recipient_message_tuples:
            logger.error(
                "failed to send emails. Empty recipient list",
                extra={"subject": subject, "from_email": from_email},
            )
            return False

        try:
            messages = [
                (subject, message, html_message, from_email, [recipient])
                for recipient, message, html_message in recipient_message_tuples
            ]

            delivered_messages = EmailService.send_mass_html_mail(
                messages,
                auth_user=auth_user,
                auth_password=auth_password,
                connection=connection,
                fail_silently=False,
                headers=headers,
            )
            logger.info(f"sent {delivered_messages} emails")

        except Exception:
            logger.exception(
                "Failed to send emails",
                extra={
                    "subject": subject,
                    "from_email": from_email,
                    "recipients": [r for r, _, _ in recipient_message_tuples],
                },
            )
            return False

        return True

    @staticmethod
    def send_personalized_emails(
        subject,
        messages,
        from_email,
        recipient_list,
        auth_user=None,
        auth_password=None,
        connection=None,
        html_messages=None,
        headers: dict[str, Any] | None = None,
    ):
        if len(recipient_list) != len(messages):
            logger.error(
                "Mismatched lengths: recipient_list and messages must be the same size",
                extra={"subject": subject, "from_email": from_email},
            )
            return False

        if html_messages and len(html_messages) != len(recipient_list):
            logger.error(
                "Mismatched lengths: recipient_list and html_messages must be the same size",
                extra={"subject": subject, "from_email": from_email},
            )
            return False

        recipient_message_tuples = [
            (recipient, message, html_messages[i] if html_messages else None)
            for i, (recipient, message) in enumerate(zip(recipient_list, messages))
        ]

        return EmailService._send_emails(
            subject,
            from_email,
            recipient_message_tuples,
            auth_user=auth_user,
            auth_password=auth_password,
            connection=connection,
            headers=headers,
        )

    @staticmethod
    def send_email(
        subject,
        message,
        from_email,
        recipient_list,
        auth_user=None,
        auth_password=None,
        connection=None,
        html_message=None,
        headers: dict[str, Any] | None = None,
    ):
        recipient_message_tuples = [(recipient, message, html_message) for recipient in recipient_list]
        return EmailService._send_emails(
            subject,
            from_email,
            recipient_message_tuples,
            auth_user=auth_user,
            auth_password=auth_password,
            connection=connection,
            headers=headers,
        )

    @staticmethod
    def send_analysis_started_email(organization):
        if not settings.SEND_ANALYSIS_STARTED_EMAIL_ACTIVE:
            logger.info("Skipping sending analysis started email")
            return False

        email_addresses = []
        if organization.connection_issued_by:
            email_addresses.append(organization.connection_issued_by.email)
        if settings.ANALYSIS_COMPLETE_EMAIL:
            email_addresses.append(settings.ANALYSIS_COMPLETE_EMAIL)
        if not email_addresses:
            return False

        contact_us_url = f"{settings.SITE_DOMAIN}{reverse('contact')}"

        message = render_to_string(
            "mvp/ai_code_monitor/analysis_started_email.html",
            {
                "organization": organization,
                "contact_us_url": contact_us_url,
                "APP_NAME": settings.APP_NAME,
            },
        )
        delivered_messages = 0
        subject = f"{settings.APP_NAME} Started Processing"
        try:
            delivered_messages = send_mass_mail(
                [
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email_to],
                    )
                    for email_to in email_addresses
                ],
                fail_silently=False,
            )

        except Exception as e:
            with push_scope() as scope:
                scope.set_extra("subject", subject)
                scope.set_extra("message", message)
                scope.set_extra("from_email", settings.DEFAULT_FROM_EMAIL)
                scope.set_extra("recipient_list", json.dumps(email_addresses))
            traceback_on_debug()
            capture_exception(e)
            logger.exception(f"failed to send analysis started email to {email_addresses}")

        finally:
            return delivered_messages > 0

    @staticmethod
    def send_import_done_email(organization):
        if not settings.SEND_IMPORT_DONE_EMAIL_ACTIVE:
            logger.info("Skipping sending import done email")
            return False

        email_addresses = []
        if organization.connection_issued_by:
            email_addresses.append(organization.connection_issued_by.email)
        if settings.ANALYSIS_COMPLETE_EMAIL:
            email_addresses.append(settings.ANALYSIS_COMPLETE_EMAIL)
        if not email_addresses:
            return False

        message = render_to_string(
            "mvp/ai_code_monitor/analysis_done_email.html",
            {
                "organization": organization,
                "url": settings.SITE_DOMAIN,
                "APP_NAME": settings.APP_NAME,
            },
        )

        delivered_messages = 0
        subject = f"{settings.APP_NAME} Finished Processing"
        try:
            delivered_messages = send_mass_mail(
                [
                    (
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email_to],
                    )
                    for email_to in email_addresses
                ],
                fail_silently=False,
            )

        except Exception as e:
            with push_scope() as scope:
                scope.set_extra("subject", subject)
                scope.set_extra("message", message)
                scope.set_extra("from_email", settings.DEFAULT_FROM_EMAIL)
                scope.set_extra("recipient_list", json.dumps(email_addresses))
            traceback_on_debug()
            capture_exception(e)
            logger.exception(f"failed to send analysis done email to {email_addresses}")
        finally:
            return delivered_messages > 0

import logging
from typing import Any, NamedTuple

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


class MultiEmailData(NamedTuple):
    subject: str
    message_txt: str
    message_html: str | None
    sender_email: str
    recipient_emails: list[str]


class EmailService:
    def __init__(self, fail_silently=False, auth_user=None, auth_password=None, connection=None, is_dry_run=False):
        self.fail_silently = fail_silently
        self.auth_user = auth_user
        self.auth_password = auth_password
        self.connection = connection
        self.is_dry_run = is_dry_run

    def get_connection(self):
        """Return connection to email backend.

        can be used as a method or as a context manager to preserve a connection
        since all email backends implement __enter__ and __exit__
        """
        if not self.connection:
            self.connection = get_connection(
                username=self.auth_user,
                password=self.auth_password,
                fail_silently=self.fail_silently,
            )
        return self.connection

    def send_mass_html_mail(
        self,
        messages_data: list[MultiEmailData],
        headers: dict[str, Any] | None = None,
    ) -> int:
        """Based on django.core.mail.send_mass_mail.

        Given a data_tuple of (subject, message, html_message, from_email,
        recipient_list), sends each message to each recipient list. Returns the
        number of emails sent.

        If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
        If auth_user and auth_password are set, they're used to log in.
        If auth_user is None, the EMAIL_HOST_USER setting is used.
        If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

        """
        messages = []
        for email_details in messages_data:
            message = EmailMultiAlternatives(
                subject=email_details.subject,
                body=email_details.message_txt,
                from_email=email_details.sender_email,
                to=email_details.recipient_emails,
                headers=headers,
            )
            if email_details.message_html:
                message.attach_alternative(email_details.message_html, "text/html")
            messages.append(message)

        if self.is_dry_run:
            logger.info("Dry run mode enabled. Emails will not be sent.")
            for email in messages:
                html_content = next(
                    (body for body, mime in getattr(email, "alternatives", []) if mime == "text/html"),
                    None,
                )
                logger.info(
                    "[dry-run] Prepared email",
                    extra={
                        "subject": email.subject,
                        "recipient": email.to,
                        "body": email.body,
                        "html_body": html_content,
                    },
                )
            return len(messages)

        connection = self.get_connection()
        return connection.send_messages(messages)

    def send_email(
        self,
        subject,
        message,
        from_email,
        recipient_list,
        html_message=None,
        headers: dict[str, Any] | None = None,
    ) -> bool:
        messages = [
            MultiEmailData(
                subject=subject,
                message_txt=message,
                message_html=html_message,
                sender_email=from_email,
                recipient_emails=[recipient],
            )
            for recipient in recipient_list
        ]
        if not messages:
            logger.error(
                "failed to send emails. Empty recipient list",
                extra={"subject": subject, "from_email": from_email},
            )
            return False

        delivered_messages_count = 0
        try:
            delivered_messages_count = self.send_mass_html_mail(
                messages,
                headers=headers,
            )
            logger.info(f"sent {delivered_messages_count} emails")
        except Exception:
            logger.exception(
                "Failed to send emails",
                extra={
                    "subject": subject,
                    "from_email": from_email,
                    "recipients": recipient_list,
                },
            )
            return False
        return delivered_messages_count > 0

    def send_analysis_started_email(self, organization):
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
        subject = f"{settings.APP_NAME} Started Processing"
        delivered_messages_count = self.send_mass_html_mail(
            [
                MultiEmailData(
                    subject=subject,
                    message_txt=message,
                    message_html=message,
                    sender_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_emails=[email_to],
                )
                for email_to in email_addresses
            ],
        )
        return delivered_messages_count > 0

    def send_import_done_email(self, organization):
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

        subject = f"{settings.APP_NAME} Finished Processing"
        delivered_messages_count = self.send_mass_html_mail(
            [
                MultiEmailData(
                    subject=subject,
                    message_txt=message,
                    message_html=message,
                    sender_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_emails=[email_to],
                )
                for email_to in email_addresses
            ],
        )
        return delivered_messages_count > 0

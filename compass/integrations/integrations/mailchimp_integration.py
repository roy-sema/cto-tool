import logging

import mailchimp_marketing as MailchimpMarketing
from django.conf import settings
from mailchimp_marketing.api_client import ApiClientError

from mvp.models import CustomUser

logger = logging.getLogger(__name__)


class MailChimpIntegration:
    LIST_ID = settings.MAILCHIMP_AUDIENCE_LIST_ID
    CONTACT = settings.MAILCHIMP_AUDIENCE_CONTACT
    PERMISSION_REMINDER = settings.MAILCHIMP_AUDIENCE_PERMISSION_REMINDER
    CAMPAIGN_DEFAULTS = settings.MAILCHIMP_AUDIENCE_CAMPAIGN_DEFAULTS

    # NOTE: Mailchimp enforces a 10-character limit on custom field tags.
    # NOTE: before adding a new field, check the section "Add a new Custom Field to the Audience" in the README of this repository.
    CUSTOM_FIELDS = [
        {
            "name": "is Paid",
            "tag": "ISPAID",
            "type": "dropdown",
            "required": False,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
            "default_value": "No",
        },
        {
            "name": "Date Joined",
            "tag": "DATEJOIN",
            "type": "date",
            "required": True,
            "public": True,
        },
        {
            "name": "Organizations",
            "tag": "ORGS",
            "type": "text",
            "required": True,
            "public": True,
        },
        {
            "name": "is Active",
            "tag": "ISACTIVE",
            "type": "dropdown",
            "required": True,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
        },
        {
            "name": "Consents Marketing Notifications",
            "tag": "MARKETING",
            "type": "dropdown",
            "required": True,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
        },
        {
            "name": "Role",
            "tag": "ROLE",
            "type": "text",
            "required": True,
            "public": True,
        },
        {
            "name": "Status Checks Enabled",
            "tag": "STATUSCHK",
            "type": "dropdown",
            "required": True,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
        },
        {
            "name": "GitHub Connect",
            "tag": "GITHUBCON",
            "type": "dropdown",
            "required": True,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
        },
        {
            "name": "Azure DevOps Connected",
            "tag": "AZURECON",
            "type": "dropdown",
            "required": True,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
        },
        {
            "name": "BitBucket Connected",
            "tag": "BITBUCKCON",
            "type": "dropdown",
            "required": True,
            "public": True,
            "options": {"choices": ["Yes", "No"]},
        },
    ]
    STATUS_SUBSCRIBED = "subscribed"

    def __init__(self):
        self.client = MailchimpMarketing.Client()
        self.client.set_config(
            {
                "api_key": settings.MAILCHIMP_API_KEY,
                "server": settings.MAILCHIMP_SERVER,
            }
        )

    def test_connection(self):
        try:
            response = self.client.ping.get()
            return True, response
        except ApiClientError as error:
            return False, error

    def create_audience(
        self,
        list_name,
        contact=None,
        permission_reminder=None,
        campaign_defaults=None,
        custom_fields=None,
        email_type_option=True,
        visibility=True,
    ):
        if not contact:
            contact = self.CONTACT
        if not permission_reminder:
            permission_reminder = self.PERMISSION_REMINDER
        if not campaign_defaults:
            campaign_defaults = self.CAMPAIGN_DEFAULTS
        if not custom_fields:
            custom_fields = self.CUSTOM_FIELDS

        create_list_data = {
            "name": list_name,
            "contact": contact,
            "permission_reminder": permission_reminder,
            "campaign_defaults": campaign_defaults,
            "email_type_option": email_type_option,
            "visibility": "pub" if visibility else "prv",
        }
        try:
            response = self.client.lists.create_list(create_list_data)
        except ApiClientError as error:
            logger.exception("Error creating mailchimp audience", extra={"list_name": list_name, "error": error.text})
            return

        list_id = response["id"]
        if custom_fields:
            self.add_custom_fields(custom_fields, list_id)

        logger.info(f"Audience '{list_name}' created successfully")
        return response

    def delete_audience(self, list_id):
        try:
            response = self.client.lists.delete_list(list_id)
        except ApiClientError as error:
            logger.exception("Error deleting mailchimp audience", extra={"list_id": list_id, "error": error.text})
            return

        logger.info(f"Audience with list ID '{list_id}' deleted successfully.")
        return response

    def sync_users(self, users=None):
        if not users:
            users = CustomUser.objects.filter(
                is_staff=False,
                is_active=True,
            ).prefetch_related("organizations")

        # Getting users status from mailchimp, so we don't overwrite status.
        audience_members = self.get_audience_members()
        users_status = {member["email_address"]: member["status"] for member in audience_members}

        error_message = "Error syncing mailchimp audience"
        members = []
        for user in users:
            org = user.organizations.first()
            if not org:
                logger.info(f"Skipping user without organization: {user.email}")
                continue

            connections = org.get_connection_list()
            status = users_status.get(user.email, self.STATUS_SUBSCRIBED)
            members.append(
                {
                    "status": status,
                    "email_address": user.email,
                    "merge_fields": {
                        "FNAME": user.first_name,
                        "LNAME": user.last_name,
                        "DATEJOIN": user.date_joined.strftime("%Y-%m-%d"),
                        "ISACTIVE": "Yes" if user.is_active else "No",
                        "MARKETING": ("Yes" if user.consent_marketing_notifications else "No"),
                        "ORGS": ",".join(organization.name for organization in user.organizations.all()),
                        "ROLE": user.role().name if user.role() else "None",
                        "STATUSCHK": "Yes" if org.status_check_enabled else "No",
                        "GITHUBCON": "Yes" if "GitHub" in connections else "No",
                        "AZURECON": "Yes" if "AzureDevOps" in connections else "No",
                        "BITBUCKCON": "Yes" if "BitBucket" in connections else "No",
                    },
                }
            )
        try:
            response = self.client.lists.batch_list_members(
                list_id=self.LIST_ID,
                body={
                    "members": members,
                    "update_existing": True,
                },
            )
        except ApiClientError as error:
            logger.exception(error_message, extra={"list_id": self.LIST_ID, "error": error.text})
            return

        sync_errors = response["errors"]
        if sync_errors:
            # These are usually due to invalid email addresses or
            # email is in a state of unsubscribe or bounce.
            logger.warning(error_message, extra={"list_id": self.LIST_ID, "sync_errors": sync_errors})

        logger.info(
            f"Members synced with audience with list ID '{self.LIST_ID}': "
            f"number of new members: {len(response['new_members'])}, "
            f"number of updated members: {len(response['updated_members'])}, "
            f"number of errors: {len(sync_errors)}",
            extra={"list_id": self.LIST_ID, "sync_errors": sync_errors},
        )
        return response

    def get_audience_members(self):
        try:
            response = self.client.lists.get_list_members_info(self.LIST_ID)
        except ApiClientError as error:
            logger.exception(
                "Error getting mailchimp audience members", extra={"list_id": self.LIST_ID, "error": error.text}
            )
            return

        return response["members"]

    def sync_user_on_sign_up(self, user):
        try:
            response = self.client.lists.add_list_member(
                list_id=self.LIST_ID,
                body={
                    "email_address": user.email,
                    "status": self.STATUS_SUBSCRIBED,
                    "merge_fields": {
                        "FNAME": user.first_name,
                        "LNAME": user.last_name,
                        "DATEJOIN": user.date_joined.strftime("%Y-%m-%d"),
                        "ISACTIVE": "Yes" if user.is_active else "No",
                        "MARKETING": ("Yes" if user.consent_marketing_notifications else "No"),
                        "ORGS": "None",
                        "ROLE": user.role().name if user.role() else "None",
                        # User at this point won't have an org. When they add
                        # their org these will be updated on the nightly sync.
                        "STATUSCHK": "No",
                        "GITHUBCON": "No",
                        "AZURECON": "No",
                        "BITBUCKCON": "No",
                    },
                },
            )
            logger.info(f"Member '{user.email}' added successfully")
            return response

        except ApiClientError as error:
            logger.exception(
                "Error syncing user to mailchimp audience",
                extra={"list_id": self.LIST_ID, "user_email": user.email, "error": error.text},
            )

    def add_custom_fields(self, custom_fields, list_id=LIST_ID):
        for custom_field in custom_fields:
            self.add_custom_field(custom_field, list_id)

    def add_custom_field(self, custom_field, list_id=LIST_ID):
        custom_field_name = custom_field["name"]
        try:
            self.client.lists.add_list_merge_field(
                list_id=list_id,
                body=custom_field,
            )
            logger.info(f"Custom field '{custom_field_name}' added successfully.")
        except ApiClientError as error:
            logger.exception(
                "Error adding custom field for mailchimp audience",
                extra={"custom_field_name": custom_field_name, "list_id": list_id, "error": error.text},
            )

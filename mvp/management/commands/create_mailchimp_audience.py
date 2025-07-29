from django.conf import settings
from django.core.management import BaseCommand

from compass.integrations.integrations import MailChimpIntegration
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Creates a mailchimp audience."

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            type=str,
            help="Audience name in mailchimp.",
        )

    def handle(self, *args, **options):
        if not settings.MAILCHIMP_ACTIVE:
            self.stdout.write(self.style.WARNING("Cannot create audience. Mailchimp is not active."))
            return

        if not self.confirm():
            self.stdout.write(self.style.WARNING("Operation cancelled."))
            return

        name = options["name"]
        response = MailChimpIntegration().create_audience(list_name=name)

        self.stdout.write(self.style.SUCCESS(f"Audience successfully created. List ID: '{response['id']}'"))

        self.stdout.write(
            f"Add List ID to the MAILCHIMP_AUDIENCE_LIST_ID environmental variable.\n"
            f"To sync users run the 'sync_users_with_mailchimp' management command.\n"
            f"Once you have finished testing you can delete this audience by running "
            f"MailChimpIntegration.delete_audience and providing the List ID."
        )

    def confirm(self):
        self.stdout.write(self.style.WARNING("This command will create a new audience in Mailchimp."))

        confirmation = input("Are you sure you want to proceed? [y/N] ").lower()

        return confirmation == "y"

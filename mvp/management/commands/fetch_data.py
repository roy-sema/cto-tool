import logging

from django.core.management.base import BaseCommand, CommandError
from sentry_sdk import capture_exception, push_scope
from sentry_sdk.crons import monitor

from compass.integrations.integrations import IntegrationFactory
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import DataProviderConnection, Organization
from mvp.utils import traceback_on_debug

logger = logging.getLogger(__name__)


class Command(
    SingleInstanceCommandMixin,
    InstrumentedCommandMixin,
    BaseCommand,
):
    help = "Fetches data from an integrated API."

    @monitor(monitor_slug="fetch_data")
    def add_arguments(self, parser):
        parser.add_argument("provider", type=str, help="Name of the provider to fetch data from.")

        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

    def handle(self, *args, **options):
        provider_name = options["provider"]

        try:
            integration = IntegrationFactory().get_integration(provider_name)
        except ValueError:
            raise CommandError(f'Provider "{provider_name}" does not exist. Check casing and spelling.')

        organization_id = options.get("orgid", 0)
        if organization_id:
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist:
                raise CommandError(f'Organization with ID "{organization_id}" does not exist.')

        qs = DataProviderConnection.objects.filter(provider=integration.provider, data__isnull=False)

        if organization_id:
            qs = qs.filter(organization=organization)

        connections = qs.all()

        if not connections:
            message = f'There are no "{provider_name}" connections'
            if organization_id:
                message += f' for "{organization}"'
            raise CommandError(message)

        for connection in connections:
            self.process_connection(connection, integration)

    def process_connection(self, connection, integration):
        if not connection.is_connected():
            logger.warning(
                "Unable to fetch data as connection is disconnected.",
                extra={
                    "organization_public_id": connection.organization.public_id(),
                    "organization_name": connection.organization.name,
                    "provider_name": connection.provider.name,
                    "connection_id": connection.id,
                },
            )
            return False

        organization = connection.organization
        provider = connection.provider

        try:
            integration.fetch_data(connection)

            logger.info(f'Successfully fetched data for "{organization}" from "{provider.name}"')
        except Exception as error:
            traceback_on_debug()

            with push_scope() as scope:
                scope.set_extra("organization", organization.name)
                scope.set_extra("provider", provider.name)
                capture_exception(error)

            logger.warning(f'Error fetching data for "{organization}" from "{provider.name}"')

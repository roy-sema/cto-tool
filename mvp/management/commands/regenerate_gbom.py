import logging

from django.core.management.base import BaseCommand

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import Organization
from mvp.tasks import ExportGBOMTask

logger = logging.getLogger(__name__)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = f"Regenerates pre-computed GBOMs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgid",
            type=int,
            help="Narrow execution just to given organization ID.",
        )

    def handle(self, *args, **options):
        for organization in self.get_organizations(options.get("orgid")):
            ExportGBOMTask().generate_precomputed_gbom(organization, force=True)

    def get_organizations(self, organization_id):
        qs = Organization.objects

        if organization_id:
            qs = qs.filter(id=organization_id)

        return qs.all()

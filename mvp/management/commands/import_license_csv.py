from mvp.management.commands._base_import_csv import BaseImportCsvCommand
from mvp.mixins import SingleInstanceCommandMixin
from mvp.models import License


class Command(SingleInstanceCommandMixin, BaseImportCsvCommand):
    help = "Imports reference data from CSV."

    def delete_records(self):
        License.objects.all().delete()

    def process_row(self, row):
        License.objects.create(
            slug=row["Key"],
            short_name=row["Short name"],
            spdx=row["SPDX identifier"],
            category=row["Category"],
        )

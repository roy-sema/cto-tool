from mvp.management.commands._base_import_csv import BaseImportCsvCommand
from mvp.mixins import SingleInstanceCommandMixin
from mvp.models import MetricsChoices, ReferenceMetric, SegmentChoices


class Command(SingleInstanceCommandMixin, BaseImportCsvCommand):
    help = "Imports reference metrics data from CSV."

    def delete_records(self):
        ReferenceMetric.objects.all().delete()

    def process_row(self, row):
        for segment in SegmentChoices.choices:
            value = row[segment[0]]
            if value == "":
                continue

            ReferenceMetric.objects.create(
                metric=getattr(MetricsChoices, row["metric"].upper()),
                percentile=self.get_int_value(row, "percentile", default=None),
                segment=segment[0],
                value=value,
            )

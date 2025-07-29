from mvp.management.commands._base_import_csv import BaseImportCsvCommand
from mvp.mixins import SingleInstanceCommandMixin
from mvp.models import ReferenceRecord


class Command(SingleInstanceCommandMixin, BaseImportCsvCommand):
    help = "Imports reference records data from CSV."

    def delete_records(self):
        ReferenceRecord.objects.all().delete()

    def process_row(self, row):
        ReferenceRecord.objects.create(
            org_id=row["01-Context-Org ID"],
            org_name=row["01-Context-Org Name"],
            segment=row["01-Context-Segment"],
            code_low_risk=self.get_int_value(row, "06-Code Security-Low Risk In-File", 0),
            code_medium_risk=self.get_int_value(row, "06-Code Security-Medium Risk In-File"),
            code_high_risk=self.get_int_value(
                row,
                "06-Code Security-High Risk In-File",
            ),
            commit_change_rate=self.get_int_value(row, "Commit change rate"),
            development_activity_change_rate=self.get_int_value(row, "Development activity change rate"),
            open_source_medium_high_file_count=self.get_int_value(
                row, "05-Open Source-High + Medium-High In File Count"
            ),
            open_source_medium_high_package_count=self.get_int_value(
                row, "05-Open Source-High + Medium-High Package Count"
            ),
            cve_high_risk=self.get_int_value(row, "06-Code Security-High Risk CVEs"),
            cyber_security_high_risk=self.get_int_value(row, "07-Cyber Security-High risk sub modules"),
        )

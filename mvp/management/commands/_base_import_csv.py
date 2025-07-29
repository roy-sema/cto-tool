import re
from abc import ABC, abstractmethod

from django.core.management.base import BaseCommand
from django.db import transaction

from mvp.utils import process_csv_file


class BaseImportCsvCommand(ABC, BaseCommand):
    @abstractmethod
    def delete_records(self):
        pass

    @abstractmethod
    def process_row(self, row):
        pass

    def pre_import(self):
        pass

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file to import.")

    def handle(self, *args, **options):
        if self.confirm():
            self.stdout.write("Updating data...")
            self.update_data(options["csv_file"])
        else:
            self.stdout.write(self.style.WARNING("Operation cancelled."))

    def confirm(self):
        self.stdout.write("This command deletes all previous data and imports the new one.")
        self.stdout.write(self.style.WARNING("This operation is not reversible."))
        confirmation = input("Are you sure you want to proceed? [y/N] ").lower()

        return confirmation == "y"

    # Transaction blocks SQLite. Remove if the CSV takes too long to import
    @transaction.atomic
    def update_data(self, csv_file):
        self.delete_records()

        num_rows = self.import_csv(csv_file)

        self.stdout.write(self.style.SUCCESS("All previous records deleted."))
        self.stdout.write(self.style.SUCCESS(f"Imported {num_rows} rows."))

    def import_csv(self, file_path, delimiter=None):
        self.pre_import()
        num_rows = process_csv_file(file_path, self.process_row, delimiter=delimiter)
        return num_rows

    def get_int_value(self, row, column, default=0):
        try:
            cleaned = re.sub(r"[^\-0-9]", "", row[column])
        except KeyError:
            self.stdout.write(self.style.ERROR(f"Column '{column}' is missing. Check spelling and trailing spaces."))
            self.stdout.write("Import aborted.")
            exit()

        return int(cleaned) if cleaned else default

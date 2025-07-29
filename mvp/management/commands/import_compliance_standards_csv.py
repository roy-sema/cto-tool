from abc import ABC

from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction

from mvp.management.commands._base_import_csv import BaseImportCsvCommand
from mvp.mixins import SingleInstanceCommandMixin
from mvp.models import (
    ComplianceStandard,
    ComplianceStandardAIUsage,
    ComplianceStandardOrganizationSizeChoices,
    ComplianceStandardReference,
    ComplianceStandardRiskLevelChoices,
    ComplianceStandardRiskTypeChoices,
    ComplianceStandardSourceChoices,
    ComplianceStandardStatusChoices,
    Geography,
    Industry,
)

STATUS_MAP = {
    "1-Contemplated": ComplianceStandardStatusChoices.CONTEMPLATED,
    "2-Proposed": ComplianceStandardStatusChoices.PROPOSED,
    "3-Close to implementation": ComplianceStandardStatusChoices.CLOSE_TO_IMPLEMENTATION,
    "4-Partially in effect": ComplianceStandardStatusChoices.PARTIALLY_IN_EFFECT,
    "5-Fully implemented": ComplianceStandardStatusChoices.FULLY_IMPLEMENTED,
    "6-To be Determined": ComplianceStandardStatusChoices.TO_BE_DETERMINED,
}

RISK_LEVEL_MAP = {
    "1-Critical": ComplianceStandardRiskLevelChoices.CRITICAL,
    "2-High": ComplianceStandardRiskLevelChoices.HIGH,
    "3-Medium": ComplianceStandardRiskLevelChoices.MEDIUM,
    "4-Low": ComplianceStandardRiskLevelChoices.LOW,
    "5-To be determined": ComplianceStandardRiskLevelChoices.TO_BE_DETERMINED,
}

SOURCE_MAP = {
    "1-Internal": ComplianceStandardSourceChoices.INTERNAL,
    "2-Government": ComplianceStandardSourceChoices.GOVERNMENT,
    "3-Other Stakeholders": ComplianceStandardSourceChoices.OTHER_STAKEHOLDERS,
}

RISK_TYPE_MAP = {
    "1-Strategic": ComplianceStandardRiskTypeChoices.STRATEGIC,
    "2-Operational": ComplianceStandardRiskTypeChoices.OPERATIONAL,
}

ORGANIZATION_SIZE_MAP = {
    "1-Firms of Any size": ComplianceStandardOrganizationSizeChoices.ANY_SIZE,
    "2-SMEs (10-249 Employees)": ComplianceStandardOrganizationSizeChoices.SME,
    "3-Large Firms (250 Employees)": ComplianceStandardOrganizationSizeChoices.LARGE,
    "4-Multinational Enterprises": ComplianceStandardOrganizationSizeChoices.MULTINATIONAL,
}

# used to pre-fill the ComplianceStandardAIUsage model
AI_USAGES = [
    "Product Functionality",
    "Internal Tools",
    "Provided by Vendor",
    "Software Development",
]

# fields that are safe to add as is
SAFE_FIELDS = [
    "name",
    "remediation_mitigation",
    "sema_source",
    "third_party_source_unique_id",
    "description",
    "policy_instrument_type_(OECD)",
    "exclude?",
]


class Command(SingleInstanceCommandMixin, BaseImportCsvCommand, ABC):
    help = "Imports compliance standards from CSV."

    def delete_records(self):
        # we don't want to delete anything
        pass

    def confirm(self):
        self.stdout.write("This command tries to update existing records and creates new ones if needed")
        confirmation = input("Are you sure you want to proceed? [y/N] ").lower()
        return confirmation == "y"

    @transaction.atomic
    def update_data(self, csv_file):
        num_rows = self.import_csv(csv_file)

        self.stdout.write(self.style.SUCCESS(f"Imported {num_rows} rows."))

    def pre_import(self):
        for ai_usage in AI_USAGES:
            ComplianceStandardAIUsage.objects.get_or_create(name=ai_usage)

    def process_row(self, row):
        geography = row["geography"].strip()
        geographies = [Geography.objects.get(name__iexact=geography)]

        industry = row["industry"].strip()
        industries = [Industry.objects.get_or_create(name=industry)[0]] if industry != "All" else None

        ai_usage = row["ai_usage"].strip()
        ai_usages = (
            ComplianceStandardAIUsage.objects.filter(name__in=map(str.strip, ai_usage.split(",")))
            if ai_usage != "To be determined"
            else None
        )

        external_id = int(row["unique_id"].strip())

        standard, _created = ComplianceStandard.objects.update_or_create(
            external_id=external_id,
            defaults={field: row[field].strip() for field in SAFE_FIELDS}
            | {
                "risk_level": RISK_LEVEL_MAP[row["risk_level"].strip()],
                "status": STATUS_MAP[row["status"].strip()],
                "source": SOURCE_MAP[row["source"].strip()],
                "risk_type": RISK_TYPE_MAP[row["risk_type"].strip()],
                "organization_size_oecd": ORGANIZATION_SIZE_MAP.get(row["organization_size_(OECD)"].strip()),
            },
        )

        if industries:
            standard.industries.set(industries)
        if geographies:
            standard.geographies.set(geographies)
        if ai_usages:
            standard.ai_usage.set(ai_usages)

        for reference in map(str.strip, row["reference"].strip().split("\n")):
            reference = reference.strip()
            if reference == "":
                continue
            try:
                if reference.startswith("http"):
                    ComplianceStandardReference.objects.get_or_create(standard=standard, url=reference)
                else:
                    splits = reference.split(":", maxsplit=1)
                    if len(splits) == 2 and splits[1].strip().startswith("http"):
                        ComplianceStandardReference.objects.get_or_create(
                            standard=standard,
                            text=splits[0].strip(),
                            url=splits[1].strip(),
                        )
                    else:
                        ComplianceStandardReference.objects.get_or_create(standard=standard, text=reference)
            except MultipleObjectsReturned:
                # we don't want to have duplicate references for the same standard
                continue

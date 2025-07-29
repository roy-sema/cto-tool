import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from compass.codebasereports.services import SemaScoreService
from compass.integrations.integrations import (
    GIT_INTEGRATIONS,
    AzureDevOpsIntegration,
    BitBucketIntegration,
    CodacyIntegration,
    GitHubIntegration,
    IRadarIntegration,
    SnykIntegration,
)
from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import (
    DataProviderConnection,
    DataProviderField,
    DataProviderMember,
    DataProviderMemberProjectRecord,
    DataProviderProject,
    DataProviderRecord,
    Organization,
)
from mvp.utils import get_days


def zero_fill(index, length=5):
    return str(index).zfill(length)


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Populate the database with data to speed up development."

    INTEGRATIONS = [
        AzureDevOpsIntegration,
        BitBucketIntegration,
        GitHubIntegration,
        CodacyIntegration,
        IRadarIntegration,
        SnykIntegration,
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--org_prefix",
            type=str,
            default="DevOrg_",
            help="Prefix for organization.",
        )

        parser.add_argument(
            "--projects_num",
            type=int,
            default=4,
            help="Number of projects per integration.",
        )

        parser.add_argument(
            "--members_num",
            type=int,
            default=10,
            help="Number of members per integration.",
        )

        parser.add_argument(
            "--days_ago",
            type=int,
            default=30,
            help="Days ago to start creating data.",
        )

        parser.add_argument(
            "--record_max_value",
            type=int,
            default=20,
            help="Max value for record.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.TESTING:
            self.stdout.write(self.style.ERROR("This command is intended for development purposes only."))
            return

        if not self.confirm():
            self.stdout.write(self.style.WARNING("Operation cancelled."))
            return

        self.config = options

        organization = self.populate_db()

        self.stdout.write(self.style.SUCCESS(f"Data populated to organization '{organization.name}'!"))

    def confirm(self):
        self.stdout.write(
            "This command adds a lot of data to the database for development. It is NOT intended for production."
        )

        self.stdout.write(self.style.WARNING("\nThis operation may be hard to reverse."))

        confirmation = input(f"Are you sure you want to generate the data? [y/N] ").lower()

        return confirmation == "y"

    def populate_db(self):
        organization = self.create_organization()
        until = timezone.now()
        since = until - timedelta(days=self.config["days_ago"])
        days = get_days(since, until)

        for integration in self.INTEGRATIONS:
            self.process_integration(
                organization,
                integration(),
                days,
                is_git_integration=integration in GIT_INTEGRATIONS,
            )

        score_service = SemaScoreService(organization)
        score_service.calculate_daily_scores()

        return organization

    def create_organization(self):
        return Organization.objects.create(name=self.get_org_name(), status_check_enabled=True)

    def get_org_name(self):
        organization_names = self.get_organization_names()

        index = 0
        while True:
            org_name = f"{self.config['org_prefix']}{zero_fill(index + 1)}"
            if org_name not in organization_names:
                return org_name

            index += 1

    def get_organization_names(self):
        return Organization.objects.only("name").values_list("name", flat=True)

    def process_integration(self, organization, integration, days, is_git_integration=False):
        connection = DataProviderConnection.objects.create(
            organization=organization,
            provider=integration.provider,
            data={"fake": "data"},
        )

        integration.get_or_create_fields()

        fields = DataProviderField.objects.filter(provider=integration.provider)

        projects = self.create_projects(organization, integration, fields.all(), days)

        if is_git_integration:
            git_fields = fields.filter(name__in=[integration.FIELD_COMMIT_COUNT]).all()
            self.create_members(organization, integration, projects, git_fields, days)

        integration.update_last_fetched(connection)

    def create_projects(self, organization, integration, fields, days):
        projects = []
        for _ in range(self.config["projects_num"]):
            project = DataProviderProject.objects.create(
                organization=organization,
                provider=integration.provider,
                name=Faker().company(),
                external_id=Faker().uuid4(),
            )
            projects.append(project)

            self.create_records(project, fields, days)

        return projects

    def create_records(self, project, fields, days):
        records = []
        for day in days:
            for field in fields:
                records.append(
                    DataProviderRecord(
                        project=project,
                        field=field,
                        value=random.randint(0, self.config["record_max_value"]),
                        date_time=day,
                    )
                )

        DataProviderRecord.objects.bulk_create(records)

    def create_members(self, organization, integration, projects, fields, days):
        for _ in range(self.config["members_num"]):
            member = DataProviderMember.objects.create(
                organization=organization,
                provider=integration.provider,
                name=Faker().name(),
                external_id=Faker().uuid4(),
            )

            self.create_member_project_records(member, projects, fields, days)

    def create_member_project_records(self, member, projects, fields, days):
        for project in projects:
            records = []
            for day in days:
                for field in fields:
                    records.append(
                        DataProviderMemberProjectRecord(
                            member=member,
                            project=project,
                            field=field,
                            value=random.randint(0, self.config["record_max_value"]),
                            date_time=day,
                        )
                    )

            DataProviderMemberProjectRecord.objects.bulk_create(records)

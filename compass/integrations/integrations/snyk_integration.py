import logging
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from sentry_sdk import capture_message

from compass.integrations.apis import SnykRestApi, SnykV1Api
from compass.integrations.integrations import BaseIntegration
from mvp.models import (
    DataProviderConnection,
    DataProviderRecord,
    License,
    LicenseCategoryChoices,
    ModuleChoices,
)
from mvp.utils import get_class_constants

logger = logging.getLogger(__name__)


class SnykIssueSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SnykIssueType:
    LICENSE = "license"
    SAST = "sast"
    VULNERABILITY = "vuln"


class SnykLicenseSeverity:
    LOW = "low"
    MEDIUM = "medium"
    MEDIUM_HIGH = "medium_high"
    HIGH = "high"


class SnykIntegration(BaseIntegration):
    DAY_FORMAT = "%Y-%m-%d"

    FIELD_SEVERITY_ISSUES_TEMPLATE = "snyk_issue_count_{type}_{level}"

    LICENSE_CATEGORY_SEVERITY_MAP = {
        LicenseCategoryChoices.COPYLEFT: SnykLicenseSeverity.HIGH,
        LicenseCategoryChoices.COPYLEFT_LIMITED: SnykLicenseSeverity.MEDIUM_HIGH,
        LicenseCategoryChoices.PERMISSIVE: SnykLicenseSeverity.LOW,
        LicenseCategoryChoices.PUBLIC_DOMAIN: SnykLicenseSeverity.LOW,
    }
    LICENSE_CATEGORY_SEVERITY_DEFAULT = SnykLicenseSeverity.MEDIUM

    SEVERITY_ISSUE_TYPES = list(get_class_constants(SnykIssueType).values())

    SEVERITY_LEVELS = list(get_class_constants(SnykIssueSeverity).values())

    SEVERITY_LICENSE_LEVELS = list(get_class_constants(SnykLicenseSeverity).values())

    @property
    def modules(self):
        return [ModuleChoices.CODE_SECURITY, ModuleChoices.OPEN_SOURCE]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._licenses_df = None
        self._spdx_url_license_map = {}

    def fetch_data(self, connection):
        self.init_connection(connection)

        self.fields = self.get_or_create_fields()

        logger.info("Retrieving projects...")
        projects = self.fetch_projects(connection.organization)
        logger.info(f"{len(projects)} projects found")

        self.fetch_issue_count(projects)

        self.update_last_fetched(connection)

    def fetch_projects(self, organization):
        projects = []

        projects_data = self.api_rest.list_projects(self.snyk_org_id, all_pages=True)
        for project_data in projects_data:
            project_id = project_data["id"]
            project_name = project_data["attributes"]["name"]
            project = self.get_or_update_project(organization, project_name, project_id, project_data)
            projects.append(project)

        return projects

    def fetch_issue_count(self, projects):
        for project in projects:
            since, until = self.get_since_until(project)

            # Skip since X 23:59:59 until X+1 00:00:00
            if (until - since).total_seconds() <= 1:
                continue

            logger.info(f"Retrieving issues for project '{project.name}' since {since} until {until}")

            issue_counts = self.get_historic_issue_counts(project.external_id, since, until, project)

            for issue_count in issue_counts.values():
                for issue_type, issue_types in issue_count["counts"].items():
                    for level, value in issue_types.items():
                        DataProviderRecord.objects.create(
                            project=project,
                            field=self.fields[issue_type][level],
                            value=value,
                            date_time=issue_count["created_at"],
                        )

    def get_historic_issue_counts(self, project_id, since, until, project):
        counts_by_day = {}

        snapshots = self.api_v1.project_history(self.snyk_org_id, project_id, all_pages=True)
        project_counts = self.get_project_counts_per_day(project_id, snapshots, since, until)

        for day, project in project_counts.items():
            if day not in counts_by_day:
                counts_by_day[day] = project
                continue

            if project["created_at"] > counts_by_day[day]["created_at"]:
                counts_by_day[day]["created_at"] = project["created_at"]

            for issue_type in self.SEVERITY_ISSUE_TYPES:
                levels = self.get_issue_type_levels(issue_type)
                for level in levels:
                    counts_by_day[day]["counts"][issue_type][level] += project["counts"][issue_type][level]

        return counts_by_day

    def get_project_counts_per_day(self, project_id, snapshots, since, until):
        project_counts = {}
        for snapshot in snapshots:
            created_at = timezone.make_aware(datetime.strptime(snapshot["created"], SnykV1Api.DATE_FORMAT))
            if created_at <= since or created_at > until:
                continue

            # snapshots are given in reverse chronological order, we keep the most recent of each day
            day = created_at.strftime(self.DAY_FORMAT)
            if day in project_counts:
                continue

            snapshot_counts = {key: dict.fromkeys(self.SEVERITY_LEVELS, 0) for key in self.SEVERITY_ISSUE_TYPES}
            for issue_type, issue_count in snapshot["issueCounts"].items():
                if issue_type not in snapshot_counts:
                    continue

                for level in self.SEVERITY_LEVELS:
                    snapshot_counts[issue_type][level] += issue_count.get(level, 0)

            # We implement a custom count for license issues
            license_issues = snapshot_counts.get(SnykIssueType.LICENSE)
            num_license_issues = sum(license_issues.values()) if license_issues else 0
            snapshot_counts[SnykIssueType.LICENSE] = (
                self.count_snapshot_license_issues(project_id, snapshot["id"])
                if num_license_issues
                else dict.fromkeys(self.SEVERITY_LICENSE_LEVELS, 0)
            )

            project_counts[day] = {
                "counts": snapshot_counts,
                "created_at": created_at,
            }

        return project_counts

    def count_snapshot_license_issues(self, project_id, snapshot_id):
        issues = self.api_v1.snapshot_issues(self.snyk_org_id, project_id, snapshot_id, types=[SnykIssueType.LICENSE])

        count = dict.fromkeys(self.SEVERITY_LICENSE_LEVELS, 0)
        for issue in issues:
            # The type filter doesn't seem to work, so let's double check
            if issue["issueType"] != SnykIssueType.LICENSE:
                continue

            severity = self.get_license_severity_level(issue["issueData"])
            count[severity] += 1

        return count

    def get_license_severity_level(self, license_data):
        return self.LICENSE_CATEGORY_SEVERITY_MAP.get(
            self.get_license_category(license_data),
            self.LICENSE_CATEGORY_SEVERITY_DEFAULT,
        )

    def get_license_category(self, license_data):
        licenses_df = self.get_licenses_df()

        license_name = license_data["title"]
        slug = license_name.lower().replace(" license", "").replace(" ", "-")
        row = licenses_df[licenses_df["slug"] == slug]
        if not row.empty:
            return row["category"].iloc[0]

        license_url = license_data["url"]
        spdx = self.fetch_spdx_license_id(license_url)
        row = licenses_df[licenses_df["spdx"] == spdx]
        if not row.empty:
            return row["category"].iloc[0]

        capture_message(f"License not found: {license_name}")
        return None

    def fetch_spdx_license_id(self, url):
        if url in self._spdx_url_license_map:
            return self._spdx_url_license_map[url]

        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        license_id_tag = soup.find("code", {"property": "spdx:licenseId"})

        if license_id_tag:
            return license_id_tag.text
        else:
            capture_message(f"Could not find SPDX license ID for URL: {url}")
            return None

    def get_licenses_df(self):
        if self._licenses_df is None:
            self._licenses_df = pd.DataFrame.from_records(License.objects.all().values())

        return self._licenses_df

    def get_or_create_fields(self):
        fields = {}
        for issue_type in self.SEVERITY_ISSUE_TYPES:
            fields[issue_type] = {}
            for level in self.get_issue_type_levels(issue_type):
                fields[issue_type][level] = self.get_or_create_field(
                    SnykIntegration.get_issue_count_field_name(issue_type, level)
                )

        return fields

    def init_connection(self, connection):
        api_token = connection.data["api_token"]
        self.api_rest = SnykRestApi(api_token)
        self.api_v1 = SnykV1Api(api_token)

        self.snyk_org_id = connection.data["org_id"]

    @staticmethod
    def get_issue_type_levels(issue_type):
        return (
            SnykIntegration.SEVERITY_LICENSE_LEVELS
            if issue_type == SnykIssueType.LICENSE
            else SnykIntegration.SEVERITY_LEVELS
        )

    @staticmethod
    def get_issue_count_field_name(issue_type, level):
        return SnykIntegration.FIELD_SEVERITY_ISSUES_TEMPLATE.format(type=issue_type, level=level)

    @staticmethod
    def get_issue_count_field_names():
        return [
            SnykIntegration.get_issue_count_field_name(issue_type, level)
            for issue_type in SnykIntegration.SEVERITY_ISSUE_TYPES
            for level in SnykIntegration.get_issue_type_levels(issue_type)
        ]

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return bool(connection.data and connection.data.get("api_token") and connection.data.get("org_id"))

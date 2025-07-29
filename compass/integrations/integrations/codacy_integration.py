import logging
from datetime import datetime

from django.utils import timezone

from compass.integrations.apis import CodacyApi
from compass.integrations.integrations import BaseIntegration
from mvp.models import DataProviderConnection, DataProviderRecord, ModuleChoices
from mvp.utils import get_class_constants

logger = logging.getLogger(__name__)


class CodacyIssueCategory:
    # Docs: https://docs.codacy.com/faq/code-analysis/which-metrics-does-codacy-calculate/#issues
    # NOTE: the IDs were obtained by interacting with the API, they are not documented
    CATEGORIES = [
        {"id": 1, "name": "Code Style"},
        {"id": 2, "name": "Security"},
        {"id": 4, "name": "Error Prone"},
        {"id": 6, "name": "Performance"},
        {"id": 7, "name": "Compatibility"},
        {"id": 8, "name": "Code Complexity"},
        {"id": 9, "name": "Documentation"},
        {"id": 11, "name": "Unused Code"},
        # NOTE: I believe we decided to exclude these categories because
        # they are not issues that Sema consider on their reports
        # Best practice
        # Comprehensibility
    ]

    CATEGORY_IDS = [category["id"] for category in CATEGORIES]

    @classmethod
    def get_by_id(cls, category_id):
        if category_id in cls.CATEGORY_IDS:
            category_index = cls.CATEGORY_IDS.index(category_id)
            return cls.format_category(cls.CATEGORIES[category_index])

        raise ValueError(f"Invalid category id: {category_id}")

    @classmethod
    def get_all(cls):
        return [cls.format_category(category) for category in cls.CATEGORIES]

    @classmethod
    def format_category(cls, category):
        return {
            "name": category["name"],
            "type": category["name"].replace(" ", ""),
            "field": category["name"].lower().replace(" ", "_"),
        }


class CodacyIntegration(BaseIntegration):
    DAY_FORMAT = "%Y-%m-%d"

    # CAUTION
    # Constants named FIELD_ will automatically create fields.
    # Check get_or_create_fields() in this file.
    FIELD_COMPLEXITY_TOTAL = "codacy_complexity_total"
    FIELD_COMPLEXITY_NUM_FILES = "codacy_complexity_num_files"
    FIELD_COMPLEXITY_FILES_PERCENTAGE = "codacy_complexity_files_percentage"

    FIELD_COVERAGE_PERCENTAGE = "codacy_coverage_percentage"
    FIELD_COVERAGE_NUM_FILES_UNCOVERED = "codacy_coverage_num_files_uncovered"

    FIELD_DUPLICATION_NUM_LINES = "codacy_duplication_num_lines"
    FIELD_DUPLICATION_PERCENTAGE = "codacy_duplication_percentage"

    FIELD_ISSUES_TOTAL = "codacy_issues_total"
    FIELD_ISSUES_PERCENTAGE = "codacy_issues_percentage"
    FIELD_ISSUES_CATEGORY_TEMPLATE = "codacy_issues_category_{category}"

    FIELD_NUM_LINES = "codacy_num_lines"

    FIELD_TECH_DEBT = "codacy_tech_debt"

    ISSUE_CATEGORIES = [category["field"] for category in CodacyIssueCategory.get_all()]

    MAPPING_FIELDS = {
        "complexFilesPercentage": FIELD_COMPLEXITY_FILES_PERCENTAGE,
        "coveragePercentageWithDecimals": FIELD_COVERAGE_PERCENTAGE,
        "duplicationPercentage": FIELD_DUPLICATION_PERCENTAGE,
        "issuePercentage": FIELD_ISSUES_PERCENTAGE,
        "numberComplexFiles": FIELD_COMPLEXITY_NUM_FILES,
        "numberDuplicatedLines": FIELD_DUPLICATION_NUM_LINES,
        "numberFilesUncovered": FIELD_COVERAGE_NUM_FILES_UNCOVERED,
        "numberIssues": FIELD_ISSUES_TOTAL,
        "numberLoc": FIELD_NUM_LINES,
        "techDebt": FIELD_TECH_DEBT,
        "totalComplexity": FIELD_COMPLEXITY_TOTAL,
    }

    @property
    def modules(self):
        return [ModuleChoices.CODE_QUALITY]

    def fetch_data(self, connection):
        self.init_connection(connection)
        self.organization = connection.organization

        self.fields = self.get_or_create_fields()

        # TODO: allow users to select organization(s)
        logger.info("Retrieving repositories...")
        projects = self.fetch_projects()
        logger.info(f"{len(projects)} repositories found")

        if projects:
            self.fetch_statistics(projects)

        self.update_last_fetched(connection)

    def fetch_projects(self):
        projects = []

        remote_orgs = self.api.list_user_organizations(all_pages=True)
        for remote_org in remote_orgs:
            remote_org_name = remote_org["name"]
            remote_org_provider = remote_org["provider"]
            repositories = self.api.list_organization_repositories_with_analysis(
                remote_org_provider, remote_org_name, all_pages=True
            )
            for repository in repositories:
                # Skip repositories that have never been analysed,
                # due to lack of credits or other problems
                if "lastAnalysedCommit" not in repository:
                    continue

                repository_id = repository["repository"]["repositoryId"]
                repository_name = repository["repository"]["name"]

                project = self.get_or_update_project(
                    self.organization,
                    repository_name,
                    repository_id,
                    {
                        "repository": repository["repository"],
                        "organization": remote_org,
                    },
                )
                projects.append(project)

        return projects

    def fetch_statistics(self, projects):
        for project in projects:
            since, until = self.get_since_until(project)

            # Skip since X 23:59:59 until X+1 00:00:00
            if (until - since).total_seconds() <= 1:
                continue

            logger.info(f"Retrieving statistics for project '{project.name}' since {since} until {until}")

            stats_by_day = self.get_stats_by_day(project, since, until)

            for stat in stats_by_day.values():
                for api_key, field_name in self.MAPPING_FIELDS.items():
                    if api_key in stat:
                        self.record_stat(project, field_name, stat[api_key], stat["created_at"])

                if "issuesPerCategory" in stat:
                    for issuesCategory in stat["issuesPerCategory"]:
                        categoryId = issuesCategory["categoryId"]

                        try:
                            category = CodacyIssueCategory.get_by_id(categoryId)["field"]
                        except ValueError:
                            continue

                        value = issuesCategory["numberOfIssues"]
                        self.record_stat(project, category, value, stat["created_at"])

    def record_stat(self, project, field_name, value, created_at):
        DataProviderRecord.objects.create(
            project=project,
            field=self.fields[field_name],
            value=value,
            date_time=created_at,
        )

    def get_stats_by_day(self, project, since, until):
        num_days = (until - since).days
        if not num_days:
            return {}

        stats = self.api.list_commit_analysis_stats(
            project.meta["repository"]["provider"],
            project.meta["organization"]["name"],
            project.name,
            num_days,
        )

        stats_by_day = {}
        for stat in stats:
            created_at = timezone.make_aware(datetime.strptime(stat["commitTimestamp"], CodacyApi.DATE_FORMAT))

            if created_at <= since or created_at > until:
                continue

            # stats are given in reverse chronological order, we keep the most recent of each day
            day = created_at.strftime(self.DAY_FORMAT)
            if day in stats_by_day:
                continue

            stats_by_day[day] = {
                **stat,
                "created_at": created_at,
            }

        return stats_by_day

    def get_or_create_fields(self):
        constants = get_class_constants(CodacyIntegration)
        field_names = [
            value for name, value in constants.items() if name.startswith("FIELD_") and "TEMPLATE" not in name
        ]
        fields = {field: self.get_or_create_field(field) for field in field_names}

        for category in self.ISSUE_CATEGORIES:
            fields[category] = self.get_or_create_field(CodacyIntegration.get_issue_category_field_name(category))

        return fields

    def init_connection(self, connection):
        self.api = CodacyApi(connection.data["api_token"])

    @staticmethod
    def get_issue_category_field_name(category):
        return CodacyIntegration.FIELD_ISSUES_CATEGORY_TEMPLATE.format(category=category)

    @staticmethod
    def get_issue_category_field_names():
        return [
            CodacyIntegration.get_issue_category_field_name(category) for category in CodacyIntegration.ISSUE_CATEGORIES
        ]

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return bool(connection.data and connection.data.get("api_token"))

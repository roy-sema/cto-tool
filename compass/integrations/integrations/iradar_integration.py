import logging
from datetime import datetime

from django.utils import timezone

from compass.integrations.apis import IRadarRestApi, IRadarXlsApi
from compass.integrations.integrations import BaseIntegration
from mvp.models import DataProviderConnection, DataProviderRecord, ModuleChoices
from mvp.utils import get_class_constants

logger = logging.getLogger(__name__)


class IRadarIssueSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IRadarIssueType:
    # We purposely don't track the commented ones
    BOTNET_LEAK = "botnet_leak"
    CVE = "cve"
    DEFAULT_LOGIN = "default_login"
    DOWNLOADABLE_FILE = "downloadable_file"
    # DNSRECORD = "dnsrecord"
    EMAIL_RISK = "email_risk"
    EXPOSED_PANEL = "exposed_panel"
    GITLEAK = "gitleak"
    # IPADDRESS = "ipaddress"
    JAVASCRIPT_KEY = "javascript_key"
    LEAKED_CREDENTIAL = "leaked_credential"
    MISCONFIGURATION = "misconfiguration"
    # PORT = "port"
    # PRE_PRODUCTION = "pre_production"
    SENSITIVE_EXPOSURE = "sensitive_exposure"
    # SUBDOMAIN = "subdomain"
    TAKEOVER = "takeover"
    # TECHNOLOGY = "technology"
    VULNERABILITY = "vulnerability"


class IRadarIntegration(BaseIntegration):
    DATA_KEYS_MAP = {
        # We purposely don't track the commented ones
        IRadarIssueType.BOTNET_LEAK: "Discovered Botnet Leaks",
        IRadarIssueType.CVE: "Discovered CVEs",
        IRadarIssueType.DEFAULT_LOGIN: "Discovered Default Logins",
        IRadarIssueType.DOWNLOADABLE_FILE: "Discovered Downloadable Files",
        # IRadarIssueType.DNSRECORD: "Discovered Dnsrecords",
        IRadarIssueType.EMAIL_RISK: "Corporate Email Risk (BEC)",
        IRadarIssueType.EXPOSED_PANEL: "Discovered Exposed Panels",
        IRadarIssueType.GITLEAK: "Discovered GitLeaks",
        # IRadarIssueType.IPADDRESS: "Discovered Ipaddress",
        IRadarIssueType.JAVASCRIPT_KEY: "Discovered Javascript Keys",
        IRadarIssueType.LEAKED_CREDENTIAL: "Discovered Leaked Credentials",
        IRadarIssueType.MISCONFIGURATION: "Discovered Misconfigurations",
        # IRadarIssueType.PORT: "Discovered Ports",
        # IRadarIssueType.PRE_PRODUCTION: "Discovered Pre Productions",
        IRadarIssueType.SENSITIVE_EXPOSURE: "Discovered Sensitive Exposures",
        # IRadarIssueType.SUBDOMAIN: "Discovered Subdomains",
        IRadarIssueType.TAKEOVER: "Discovered Takeovers",
        # IRadarIssueType.TECHNOLOGY: "Discovered Technologies",
        IRadarIssueType.VULNERABILITY: "Discovered Vulnerabilities",
    }

    FIELD_SEVERITY_ISSUES_TEMPLATE = "iradar_issue_count_{type}_{level}"
    FIELD_TOTAL_ISSUES_TEMPLATE = "iradar_total_issues_{type}"

    FIELD_KEY_TOTAL = "total"

    # TODO: add other types that have severity
    SEVERITY_ISSUE_TYPES = [
        IRadarIssueType.CVE,
    ]

    SEVERITY_LEVELS = list(get_class_constants(IRadarIssueSeverity).values())

    @property
    def modules(self):
        return [ModuleChoices.CYBER_SECURITY]

    def fetch_data(self, connection):
        self.init_connection(connection)

        self.fields = self.get_or_create_fields()

        # TODO: allow users to select organization(s) and target(s)
        # organizations = self.api_rest.list_organizations()
        logger.info("Retrieving targets...")
        projects = self.fetch_projects(connection.organization)
        logger.info(f"{len(projects)} targets found")

        if projects:
            self.fetch_scans(projects)

        self.update_last_fetched(connection)

    def fetch_projects(self, organization):
        projects = []

        targets = self.api_rest.list_targets()
        for target in targets:
            target_id = target["domainid"]
            target_name = target["domain"]
            project = self.get_or_update_project(organization, target_name, target_id, target)
            projects.append(project)

        return projects

    def fetch_scans(self, projects):
        logger.info("Retrieving scans...")
        scans = self.api_rest.list_scans()
        logger.info(f"{len(scans)} scans found")

        # Obtain just once for each project, plus avoid altering dates with new scans
        projects_since_until = {}
        for project in projects:
            projects_since_until[project.pk] = self.get_since_until(project)

        for scan in scans:
            project = self.find_scan_project(scan, projects)
            since, until = projects_since_until[project.pk]

            scan_date = timezone.make_aware(
                datetime.strptime(scan["last_scanned_on_string"], IRadarRestApi.DATE_FORMAT)
            )
            if scan_date <= since or scan_date > until:
                continue

            report = self.api_xls.download_report(scan["domain"], scan["scanid"])
            if report:
                self.process_report(report, scan_date, project)

    def process_report(self, report, scan_date, project):
        logger.info(f"Processing report for target '{project.name}' on {scan_date}")

        self.process_cve_issues(report, scan_date, project)
        self.process_submodules_total_issues(report, scan_date, project)

    def process_cve_issues(self, report, scan_date, project):
        data_key = self.DATA_KEYS_MAP[IRadarIssueType.CVE]
        if data_key not in report:
            return

        cve_issue_count = dict.fromkeys(self.SEVERITY_LEVELS, 0)
        for cve_issue in report[data_key]:
            if str(cve_issue["Severity"]) == "nan":
                continue

            severity = getattr(IRadarIssueSeverity, cve_issue["Severity"].upper())
            cve_issue_count[severity] += 1

        for severity, count in cve_issue_count.items():
            DataProviderRecord.objects.create(
                project=project,
                field=self.fields[IRadarIssueType.CVE][severity],
                value=count,
                date_time=scan_date,
            )

    def process_submodules_total_issues(self, report, scan_date, project):
        for issue_type, data_key in self.DATA_KEYS_MAP.items():
            total_issues = len(report.get(data_key, []))

            DataProviderRecord.objects.create(
                project=project,
                field=self.fields[issue_type][self.FIELD_KEY_TOTAL],
                value=total_issues,
                date_time=scan_date,
            )

    def find_scan_project(self, scan, projects):
        for project in projects:
            if project.meta["orgid"] == scan["orgid"] and project.meta["domain"] == scan["domain"]:
                return project

        raise Exception(f"Project not found for {scan['scanid']}")

    def get_or_create_fields(self):
        fields = {}
        for issue_type in self.DATA_KEYS_MAP.keys():
            fields[issue_type] = {
                self.FIELD_KEY_TOTAL: self.get_or_create_field(
                    IRadarIntegration.get_total_issues_field_name(issue_type)
                )
            }

        for issue_type in self.SEVERITY_ISSUE_TYPES:
            for level in self.SEVERITY_LEVELS:
                fields[issue_type][level] = self.get_or_create_field(
                    IRadarIntegration.get_issue_count_field_name(issue_type, level)
                )

        return fields

    def init_connection(self, connection):
        self.api_rest = IRadarRestApi()
        self.api_rest.set_auth_token(connection.data["username"], connection.data["password"])
        self.api_xls = IRadarXlsApi(self.api_rest.auth_token)

    @staticmethod
    def get_issue_count_field_name(issue_type, level):
        return IRadarIntegration.FIELD_SEVERITY_ISSUES_TEMPLATE.format(type=issue_type, level=level)

    @staticmethod
    def get_issue_count_field_names():
        return [
            IRadarIntegration.get_issue_count_field_name(issue_type, level)
            for issue_type in IRadarIntegration.SEVERITY_ISSUE_TYPES
            for level in IRadarIntegration.SEVERITY_LEVELS
        ]

    @staticmethod
    def get_total_issues_field_name(issue_type):
        return IRadarIntegration.FIELD_TOTAL_ISSUES_TEMPLATE.format(type=issue_type)

    @staticmethod
    def get_total_issues_field_names():
        return [
            IRadarIntegration.get_total_issues_field_name(issue_type)
            for issue_type in IRadarIntegration.SEVERITY_ISSUE_TYPES
        ]

    @staticmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        return bool(connection.data and connection.data.get("username") and connection.data.get("password"))

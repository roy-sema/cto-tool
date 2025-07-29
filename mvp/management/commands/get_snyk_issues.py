import logging

import pandas as pd
from django.core.management.base import BaseCommand

from compass.integrations.integrations import SnykIntegration
from mvp.models import DataProviderConnection, DataProviderProject

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetches all Snyk issues for a given target and outputs them as CSV"

    def add_arguments(self, parser):
        parser.add_argument("project_id", type=str, help="Snyk project ID")

    def handle(self, *args, **options):
        project = DataProviderProject.objects.get(external_id=options["project_id"])

        connection = DataProviderConnection.objects.get(provider=project.provider, organization=project.organization)

        snyk = SnykIntegration()
        snyk.init_connection(connection)

        issues = snyk.api_v1.project_issues(snyk.snyk_org_id, project.external_id)
        if issues:
            logger.info(self.flatten_issues_to_csv(issues))
        else:
            logger.info("No issues found")

    def flatten_issues_to_csv(self, issues):
        return pd.json_normalize(issues).to_csv(index=False)

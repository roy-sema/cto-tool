import logging
import os

from django.core.management.base import BaseCommand
from opentelemetry import trace
from sentry_sdk.crons import monitor

from compass.contextualization.tasks.import_anomaly_insights import (
    ImportGitAnomalyInsightsTask,
    ImportJiraAnomalyInsightsTask,
)
from compass.contextualization.tasks.import_daily_message_task import ImportDailyMessageTask
from compass.contextualization.tasks.import_pipeline_bc_data_task import ImportPipelineBCDataTask
from compass.contextualization.tasks.import_ticket_completeness_task import ImportTicketCompletenessTask
from mvp.mixins import InstrumentedCommandMixin
from mvp.models import Organization
from mvp.opentelemetry_utils import start_span_in_linked_trace
from mvp.services import ContextualizationDayInterval, ContextualizationResults, ContextualizationService
from mvp.tasks import ImportContextualizationDataTask

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class Command(InstrumentedCommandMixin, BaseCommand):
    service = ContextualizationService

    help = "Experimental: execute contextualization scripts for given organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orgids",
            type=int,
            nargs="+",
            help="Narrow execution just to given organization IDs (separated by space).",
        )

        parser.add_argument(
            "--skip-orgids",
            type=str,
            nargs="+",
            help="Skips orgs even if they have contextualization enabled (space-separated).",
        )

        parser.add_argument(
            "--day-interval",
            type=int,
            choices=[e.value for e in ContextualizationDayInterval],
            default=ContextualizationService.DEFAULT_DAY_INTERVAL.value,
            help="Day interval to be executed.",
        )

        parser.add_argument(
            "--pipelines",
            type=str,
            nargs="+",
            default=self.service.ALL_PIPELINES,
            help="Execute one or more pipelines (space-separated).",
        )

        parser.add_argument(
            "--by-group",
            action="store_true",
            help="Execute scripts by group.",
        )

        parser.add_argument(
            "--import-only",
            action="store_true",
            help="Only copy/import the data without executing the scripts.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not execute the scripts, only print the output.",
        )

    @monitor(monitor_slug="experiment_contextualization_script")
    def handle(self, *args, **options):
        day_interval_value = options["day_interval"]
        day_interval = ContextualizationDayInterval(day_interval_value)
        organization_ids = options.get("orgids", None)
        pipelines = options.get("pipelines")
        skip_orgids = options.get("skip_orgids", None)
        dry_run = options.get("dry_run", False)
        by_group = options.get("by_group", False)
        import_only = options.get("import_only", False)

        invalid_pipelines = set(pipelines) - set(self.service.ALL_PIPELINES)
        if invalid_pipelines:
            raise ValueError(f"Invalid pipelines: {', '.join(invalid_pipelines)}")

        organizations = self.service.get_organizations(organization_ids, skip_organization_ids=skip_orgids)

        # Some organizations need to be run on priority
        priority_orgs_env = os.getenv("CONTEXTUALIZATION_PRIORITY_ORGANIZATIONS")
        if priority_orgs_env:
            priority_organization_ids = [int(org_id.strip()) for org_id in priority_orgs_env.split(",")]
            organizations = sorted(organizations, key=lambda org: org.id in priority_organization_ids, reverse=True)

        logger.info("Running contextualization pipelines")
        for index, organization in enumerate(organizations):
            results = self.service.process_organization(
                organization,
                day_interval=day_interval,
                pipelines=pipelines,
                by_group=by_group,
                import_only=import_only,
                dry_run=dry_run,
            )

            if dry_run:
                continue

            if results is None:
                logger.warning(
                    f"No data was generated for organization",
                    extra={"organization": organization},
                )
                continue

            self.import_results(organization, day_interval, pipelines, results)

    @start_span_in_linked_trace(tracer, "Importing contextualization data from saved JSONs to database")
    def import_results(
        self,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
        pipelines: list[str],
        results: ContextualizationResults,
    ):
        if day_interval == ContextualizationService.DEFAULT_DAY_INTERVAL:
            if self.service.PIPELINE_A in pipelines:
                try:
                    imported = ImportContextualizationDataTask().run(organization)
                    if not imported:
                        logger.warning(
                            "No data was imported for pipeline A",
                            extra={"organization": organization, "day_interval": day_interval.value},
                        )
                except Exception:
                    logger.exception(
                        "Error on importing pipeline A",
                        extra={"organization": organization, "day_interval": day_interval.value},
                    )

            if self.service.PIPELINE_BC in pipelines and results.pipeline_b_and_c_result:
                try:
                    ImportPipelineBCDataTask().import_results(
                        organization, day_interval, results.pipeline_b_and_c_result
                    )
                except Exception:
                    logger.exception(
                        "Error importing pipeline bc",
                        extra={"organization": organization},
                    )
        elif day_interval == ContextualizationDayInterval.ONE_DAY:
            try:
                ImportDailyMessageTask().import_results(organization)
            except Exception:
                logger.exception(
                    "Error saving daily message data to db",
                    extra={"organization": organization},
                )

            try:
                if results.pipeline_d_result:
                    ImportTicketCompletenessTask().import_results(
                        organization,
                        results.pipeline_d_result.ticket_completeness_scores,
                    )
                if results.pipeline_anomaly_insights_result:
                    ImportGitAnomalyInsightsTask().import_results(
                        organization,
                        results.pipeline_anomaly_insights_result,
                    )
                if results.pipeline_jira_anomaly_insights_result:
                    ImportJiraAnomalyInsightsTask().import_results(
                        organization,
                        results.pipeline_jira_anomaly_insights_result,
                    )
            except Exception:
                logger.exception(
                    "Error saving ticket completeness data to db",
                    extra={"organization": organization},
                )

        logger.info(
            f'Successfully generated data for "{organization}"',
            extra={"organization": organization},
        )

import logging
import os

from django.core.management.base import BaseCommand
from opentelemetry import trace
from sentry_sdk.crons import monitor

from compass.contextualization.tasks import (
    ImportGitAnomalyInsightsTask,
    ImportJiraAnomalyInsightsTask,
    ImportPipelineBCDataTask,
    ImportQualitySummaryTask,
    ImportTicketCompletenessTask,
)
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
            "--import-only",
            action="store_true",
            help="Only copy/import the data without executing the scripts.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not execute the scripts, only print the output.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="(DEPRECATED, use force_anomaly_insights).",
        )
        parser.add_argument(
            "--force_anomaly_insights",
            action="store_true",
            help="Save insights even if it has already been executed today.",
        )
        parser.add_argument(
            "--force-pipeline-a", action="store_true", help="Don't use cached results in db and update them."
        )

    @monitor(monitor_slug="experiment_contextualization_script")
    def handle(self, *args, **options):
        day_interval_value = options["day_interval"]
        day_interval = ContextualizationDayInterval(day_interval_value)
        organization_ids = options.get("orgids")
        pipelines = options.get("pipelines")
        skip_orgids = options.get("skip_orgids")
        dry_run = options.get("dry_run", False)
        import_only = options.get("import_only", False)

        if options.get("force"):
            logger.warning("Force is deprecated, use pipeline specific force")

        force_anomaly_insights = options.get("force_anomaly_insights", False) or options.get("force", False)
        force_pipeline_a = options.get("force_pipeline_a", False)

        invalid_pipelines = set(pipelines) - set(self.service.ALL_PIPELINES)
        if invalid_pipelines:
            raise ValueError(f"Invalid pipelines: {', '.join(invalid_pipelines)}")

        organizations = self.service.get_organizations(organization_ids, skip_organization_ids=skip_orgids)

        # Some organizations need to be run on priority
        priority_orgs_env = os.getenv("CONTEXTUALIZATION_PRIORITY_ORGANIZATIONS")
        if priority_orgs_env:
            priority_organization_ids = [int(org_id.strip()) for org_id in priority_orgs_env.split(",")]
            organizations = sorted(organizations, key=lambda org: org.id in priority_organization_ids, reverse=True)

        logger.info(f"Running contextualization pipelines for {len(organizations)} organizations")
        for organization in organizations:
            results = self.service.process_organization(
                organization,
                day_interval=day_interval,
                pipelines=pipelines,
                import_only=import_only,
                dry_run=dry_run,
                force_pipeline_a=force_pipeline_a,
            )

            if dry_run:
                continue

            if results is None:
                logger.warning(
                    f"No data was generated for organization",
                    extra={"organization": organization.name},
                )
                continue

            self.import_results(organization, day_interval, pipelines, results, force_anomaly_insights)

    @start_span_in_linked_trace(tracer, "Importing contextualization data from saved JSONs to database")
    def import_results(
        self,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
        pipelines: list[str],
        results: ContextualizationResults,
        force_anomaly_insights: bool,
    ):
        if day_interval == ContextualizationDayInterval.TWO_WEEKS:
            if self.service.PIPELINE_A in pipelines:
                try:
                    imported = ImportContextualizationDataTask(
                        organization=organization, pipeline_results=results
                    ).run()
                    if not imported:
                        logger.warning(
                            "No data was imported for pipeline A",
                            extra={"organization": organization.name, "day_interval": day_interval.value},
                        )
                except Exception:
                    logger.exception(
                        "Error on importing pipeline A",
                        extra={"organization": organization.name, "day_interval": day_interval.value},
                    )

            if self.service.PIPELINE_BC in pipelines and results.pipeline_b_and_c_result:
                try:
                    ImportPipelineBCDataTask().import_results(
                        organization, day_interval, results.pipeline_b_and_c_result
                    )
                except Exception:
                    logger.exception(
                        "Error importing pipeline bc",
                        extra={"organization": organization.name},
                    )
        elif day_interval == ContextualizationDayInterval.ONE_DAY:
            try:
                if results.pipeline_d_result:
                    ImportTicketCompletenessTask.import_results(
                        organization,
                        results.pipeline_d_result.ticket_completeness_scores,
                    )
                    if results.pipeline_d_result.quality_summary is not None:
                        ImportQualitySummaryTask.import_results(
                            organization,
                            results.pipeline_d_result.quality_summary,
                            force=force_anomaly_insights,
                        )
            except Exception:
                logger.exception(
                    "Error saving ticket completeness data to db",
                    extra={"organization": organization.name},
                )
            try:
                if results.pipeline_anomaly_insights_result:
                    ImportGitAnomalyInsightsTask.import_results(
                        organization,
                        results.pipeline_anomaly_insights_result,
                        force=force_anomaly_insights,
                    )
            except Exception:
                logger.exception(
                    "Error saving git anomaly insights data to db",
                    extra={"organization": organization.name},
                )
            try:
                if results.pipeline_jira_anomaly_insights_result:
                    ImportJiraAnomalyInsightsTask.import_results(
                        organization,
                        results.pipeline_jira_anomaly_insights_result,
                        force=force_anomaly_insights,
                    )
            except Exception:
                logger.exception(
                    "Error saving jira anomaly insights data to db",
                    extra={"organization": organization.name},
                )

        logger.info(
            f'Successfully generated data for "{organization}"',
            extra={"organization": organization.name},
        )

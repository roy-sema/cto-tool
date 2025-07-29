import copy
import csv
import json
import logging
import os
import shutil
import textwrap
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import pandas as pd
from django.conf import settings
from django.utils import timezone
from opentelemetry import trace
from pydantic import BaseModel
from sentry_sdk import capture_exception, capture_message, push_scope

from compass.dashboard.models import GitDiffContext
from compass.integrations.apis import JiraApi, JiraApiConfig
from compass.integrations.integrations import JiraIntegration, SlackIntegration
from contextualization.pipelines.anomaly_driven_insights.main import (
    GitCombinedInsights,
    run_anomaly_driven_insights,
)
from contextualization.pipelines.insights_aggregation_pipeline.main import (
    run_insights_aggregation_pipeline,
)
from contextualization.pipelines.insights_aggregation_pipeline.schemas import InsightsAggregation
from contextualization.pipelines.jira_anomaly_driven_insights.jira_anomaly_insights import (
    JiraCombinedInsights,
    run_jira_anomaly_driven_insights_pipeline,
)
from contextualization.pipelines.pipeline_A_automated_process.main import GitAnalysisResults, run_pipeline_a
from contextualization.pipelines.pipeline_A_automated_process.main_insights import (
    run_pipeline_a_insights,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.main import (
    run_pipeline_b_c,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import PipelineBCResult
from contextualization.pipelines.pipeline_D_jira_score_completeness.jira_completeness_score import (
    PipelineDResult,
    run_jira_completeness_score_pipeline,
)
from contextualization.utils.custom_exceptions import NoCommitsFoundError
from mvp.models import (
    DataProviderConnection,
    JiraProject,
    Organization,
    Repository,
    RepositoryGroup,
)
from mvp.opentelemetry_utils import get_otel_attributes_from_parent_span, start_span_in_linked_trace
from mvp.services.initiatives_service import add_pinned_initiatives_input_prompt
from mvp.utils import traceback_on_debug

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class ContextualizationDayInterval(Enum):
    ONE_DAY = 1
    ONE_WEEK = 7
    TWO_WEEKS = 14


@contextmanager
def execute_pipeline_with_telemetry(
    pipeline_name: str,
):
    os.umask(0o002)
    span_attributes = get_otel_attributes_from_parent_span("organization", "day_interval")
    logger.info(f"Executing {pipeline_name}.", extra=span_attributes)
    with start_span_in_linked_trace(tracer, pipeline_name, prefix="cto_tool_", attributes=span_attributes):
        yield


class ContextualizationResults(BaseModel):
    pipeline_a_result: GitAnalysisResults | None = None
    pipeline_b_and_c_result: PipelineBCResult | None = None
    pipeline_d_result: PipelineDResult | None = None
    pipeline_anomaly_insights_result: GitCombinedInsights | None = None
    pipeline_jira_anomaly_insights_result: JiraCombinedInsights | None = None
    insights_aggregation: InsightsAggregation | None = None


class ContextualizationService:
    DATA_DIR_NAME = "__contextualization"
    # always at 06:00 UTC
    # TODO add timezone
    DATETIME_FORMAT = "%Y-%m-%dT06:00:00"
    DATE_FORMAT = "%Y-%m-%d"
    DATE_SLACK_FORMAT = "%Y-%m-%d %H:%M:%S"

    DEFAULT_DAY_INTERVAL = ContextualizationDayInterval.TWO_WEEKS
    DAY_INTERVAL_TWO_WEEKS_FOLDER = "__two_weeks"
    DAY_INTERVAL_ONE_WEEK_FOLDER = "__one_week"
    DAY_INTERVAL_ONE_DAY_FOLDER = "__one_day"
    DAY_INTERVALS_FOLDER_MAP = {
        ContextualizationDayInterval.TWO_WEEKS.value: DAY_INTERVAL_TWO_WEEKS_FOLDER,
        ContextualizationDayInterval.ONE_WEEK.value: DAY_INTERVAL_ONE_WEEK_FOLDER,
        ContextualizationDayInterval.ONE_DAY.value: DAY_INTERVAL_ONE_DAY_FOLDER,
    }

    UNGROUPED_LABEL = "other"

    OUTPUT_FILENAME_COUNT = "count.json"
    OUTPUT_FILENAME_JUSTIFICATION = "justification.json"
    OUTPUT_FILENAME_GROUPED_JUSTIFICATION = "grouped_justification.json"
    OUTPUT_FILENAME_PROJECTS = "projects.json"
    OUTPUT_FILENAME_INITIATIVES = "initiatives.json"
    OUTPUT_FILENAME_ROADMAP = "roadmap.json"
    OUTPUT_FILENAME_ROADMAP_RECONCILIATION = "roadmap_reconciliation.json"
    OUTPUT_FILENAME_COMBINED_ANOMALY_INSIGHTS = "combined_anomaly_insights.json"
    OUTPUT_FILENAME_INSIGHTS_AGGREGATION = "aggregated_anomaly_insights.json"
    OUTPUT_FILENAME_JIRA_COMPLETENESS_SCORE = "jira_completeness_score.json"
    OUTPUT_FILENAME_JIRA_QUALITY_SUMMARY = "jira_quality_summary.json"
    OUTPUT_FILENAME_JIRA_ANOMALY_INSIGHTS = "jira_anomaly_insights.json"

    PIPELINE_A = "a"
    PIPELINE_BC = "bc"
    PIPELINE_ANOMALY_INSIGHTS = "anomaly_insights"
    PIPELINE_INSIGHTS_AGGREGATION = "insights_aggregation"
    PIPELINE_D = "d"
    PIPELINE_JIRA_ANOMALY_INSIGHTS = "jira_anomaly_insights"

    # Pipelines that require GIT commits for the contextualization window
    GIT_PIPELINES = {
        PIPELINE_A,
        PIPELINE_BC,
        PIPELINE_ANOMALY_INSIGHTS,
        PIPELINE_INSIGHTS_AGGREGATION,
    }

    ALL_PIPELINES = {
        PIPELINE_D,
        PIPELINE_JIRA_ANOMALY_INSIGHTS,
    } | GIT_PIPELINES

    SCRIPT_OUTPUT_DIR = "git_dataset"
    SCRIPT_ALL_REPOS_OUTPUT_DIR = f"{SCRIPT_OUTPUT_DIR}/all_repos"
    SCRIPT_PIPLINE_D_SUFFIX_OUTPUT_DIR = "jira_completeness_score"
    SCRIPT_PIPLINE_JIRA_ANOMALY_INSIGHTS_SUFFIX_OUTPUT_DIR = "jira_anomaly_insights"

    SCRIPT_OUTPUT_SUFFIX_COUNT = "_git_data_count.json"
    SCRIPT_OUTPUT_SUFFIX_INITIATIVES = "_git_data_summary_git_data_initiatives.json"
    SCRIPT_OUTPUT_SUFFIX_SUMMARY = "_git_data_summary.csv"
    SCRIPT_OUTPUT_SUFFIX_SUMMARY_FINAL = "_git_data_overall_summary_final.json"
    SCRIPT_OUTPUT_SUFFIX_GIT_INITIATIVES_COMBINED = "_git_data_summary_git_data_initiatives_combined.json"

    SCRIPT_OUTPUT_SUFFIX_JIRA_INITIATIVES = "_git_data_summary_jira_initiatives.json"
    SCRIPT_OUTPUT_SUFFIX_RECONCILIATION_INSIGHTS = "_git_data_summary_reconciliation_insights.json"
    SCRIPT_OUTPUT_SUMMARY_ANOMALY_SUFFIX_OUTPUT = "_git_data_summary_anomaly_output.csv"
    SCRIPT_OUTPUT_ANOMALY_INSIGHTS_SUFFIX = "_git_anomaly_driven_insights.json"
    SCRIPT_OUTPUT_COMBINED_ANOMALY_INSIGHTS = f"combined{SCRIPT_OUTPUT_ANOMALY_INSIGHTS_SUFFIX}"
    SCRIPT_OUTPUT_INSIGHTS_AGGREGATION = "aggregated_anomaly_insights.json"
    SCRIPT_OUTPUT_JIRA_DATA_WITH_SCORE_SUMMARY_SUFFIX = "jira_data_with_score_summary.json"
    SCRIPT_OUTPUT_JIRA_DATA_WITH_QUALITY_SUMMARY_SUFFIX = "jira_quality_summary_report.json"
    SCRIPT_OUTPUT_JIRA_DATA_WITH_SCORE_SUFFIX = "jira_data_with_score.csv"
    SCRIPT_OUTPUT_JIRA_ANOMALY_INSIGHTS_SUFFIX = "jira_all_projects_skip_meeting.json"

    COPY_FILES_PIPELINE_A = {
        SCRIPT_OUTPUT_SUFFIX_COUNT: OUTPUT_FILENAME_COUNT,
        SCRIPT_OUTPUT_SUFFIX_SUMMARY_FINAL: OUTPUT_FILENAME_JUSTIFICATION,
    }

    COPY_FILES_PIPELINE_BC = {
        SCRIPT_OUTPUT_SUFFIX_INITIATIVES: OUTPUT_FILENAME_PROJECTS,
        SCRIPT_OUTPUT_SUFFIX_GIT_INITIATIVES_COMBINED: OUTPUT_FILENAME_ROADMAP,
    }

    COPY_FILES_PIPELINE_BC_WITH_JIRA = {
        **COPY_FILES_PIPELINE_BC,
        SCRIPT_OUTPUT_SUFFIX_RECONCILIATION_INSIGHTS: OUTPUT_FILENAME_ROADMAP_RECONCILIATION,
    }

    COPY_FILES_PIPELINE_D = {
        SCRIPT_OUTPUT_JIRA_DATA_WITH_SCORE_SUMMARY_SUFFIX: OUTPUT_FILENAME_JIRA_COMPLETENESS_SCORE,
        SCRIPT_OUTPUT_JIRA_DATA_WITH_QUALITY_SUMMARY_SUFFIX: OUTPUT_FILENAME_JIRA_QUALITY_SUMMARY,
    }

    COPY_FILES_PIPELINE_ANOMALY_INSIGHTS = {
        SCRIPT_OUTPUT_COMBINED_ANOMALY_INSIGHTS: OUTPUT_FILENAME_COMBINED_ANOMALY_INSIGHTS,
    }

    COPY_FILES_PIPELINE_INSIGHTS_AGGREGATION = {
        SCRIPT_OUTPUT_INSIGHTS_AGGREGATION: OUTPUT_FILENAME_INSIGHTS_AGGREGATION,
    }

    COPY_FILES_PIPELINE_JIRA_ANOMALY_INSIGHTS = {
        SCRIPT_OUTPUT_JIRA_ANOMALY_INSIGHTS_SUFFIX: OUTPUT_FILENAME_JIRA_ANOMALY_INSIGHTS,
    }

    PIPELINE_TO_COPY_FILES_MAP = {
        PIPELINE_A: COPY_FILES_PIPELINE_A,
        PIPELINE_BC: COPY_FILES_PIPELINE_BC_WITH_JIRA,
        PIPELINE_ANOMALY_INSIGHTS: COPY_FILES_PIPELINE_ANOMALY_INSIGHTS,
        PIPELINE_D: COPY_FILES_PIPELINE_D,
        PIPELINE_JIRA_ANOMALY_INSIGHTS: COPY_FILES_PIPELINE_JIRA_ANOMALY_INSIGHTS,
        PIPELINE_INSIGHTS_AGGREGATION: COPY_FILES_PIPELINE_INSIGHTS_AGGREGATION,
    }

    PIPLINE_BC_OUTPUT = [
        SCRIPT_OUTPUT_SUFFIX_JIRA_INITIATIVES,
        SCRIPT_OUTPUT_SUFFIX_INITIATIVES,
        SCRIPT_OUTPUT_SUFFIX_GIT_INITIATIVES_COMBINED,
        SCRIPT_OUTPUT_SUFFIX_RECONCILIATION_INSIGHTS,
    ]

    PIPLINE_BC_OUTPUT_DIRECTORIES = ["git_data_only", "jira_and_git", "jira_data"]

    PIPELINE_ANOMALY_INSIGHTS_OUTPUT = [
        SCRIPT_OUTPUT_SUMMARY_ANOMALY_SUFFIX_OUTPUT,
        SCRIPT_OUTPUT_ANOMALY_INSIGHTS_SUFFIX,
    ]

    ANOMALY_INSIGHTS_PER_EMAIL = 5
    ANOMALY_INSIGHTS_EMAIL_LINK = f"{settings.SITE_DOMAIN}/product-roadmap-radar/development-activity"
    ANOMALY_INSIGHTS_REPO_LOOKBACK_HOURS = 24

    @classmethod
    def process_organization(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
        pipelines=None,
        by_group=False,
        import_only=False,
        dry_run=False,
    ) -> ContextualizationResults | None:
        try:
            pipelines = pipelines or cls.ALL_PIPELINES
            contextualization_results = ContextualizationResults()
            with tracer.start_as_current_span(
                "process_organization",
                attributes={
                    "organization": organization.name,
                    "day_interval": day_interval.value,
                    "pipelines": list(pipelines),
                    "by_group": by_group,
                    "dry_run": dry_run,
                },
            ) as span:
                logger.info(
                    f"Process contextualization for organization {organization.name}",
                    extra={
                        "organization": organization.name,
                        "day_interval": day_interval.value,
                    },
                )

                if not dry_run and not import_only:
                    cls.clean_previous_data(organization, pipelines=pipelines)

                data_dir = cls.create_contextualization_directory(organization)

                start_date, end_date = cls.get_start_and_end_date(day_interval)
                jira_params = None
                repo_group_git_repos, repo_group_jira_projects = None, None
                if by_group:
                    # disable by_group if no groups
                    by_group = RepositoryGroup.objects.filter(organization=organization).exists()
                    if not by_group:
                        logger.info(
                            f"No repository groups found for {organization.name}, skipping group generation",
                            extra={"organization": organization.name},
                        )

                if not dry_run and not import_only:
                    cls.delete_symlinks(data_dir)

                    cls.create_symbolic_links(organization, data_dir)

                    if by_group:
                        repo_group_git_repos, repo_group_jira_projects = cls.generate_repository_group(organization)

                copy_files = {}

                if cls.PIPELINE_A in pipelines:
                    if not import_only:
                        pipeline_a_result = cls.execute_pipeline_a(
                            data_dir,
                            start_date,
                            end_date,
                            dry_run=dry_run,
                        )
                        if by_group:
                            # if by group then execute again but generate insights separated by group
                            pipeline_a_result = cls.execute_pipeline_a(
                                data_dir,
                                start_date,
                                end_date,
                                repo_group_git_repos=repo_group_git_repos,
                                dry_run=dry_run,
                            )

                        contextualization_results.pipeline_a_result = pipeline_a_result
                        if not pipeline_a_result.total_code_commit_count:
                            pipelines_to_skip = [p for p in pipelines if p in cls.GIT_PIPELINES]
                            pipelines = [p for p in pipelines if p not in cls.GIT_PIPELINES]
                            logger.warning(
                                "No commits found for pipeline A. Git-related pipelines will be skipped",
                                extra={"organization": organization.name, "pipelines_to_skip": pipelines_to_skip},
                            )
                        else:
                            copy_files.update(cls.COPY_FILES_PIPELINE_A)

                if cls.PIPELINE_BC in pipelines:
                    jira_params = jira_params or cls.get_jira_params(
                        organization=organization,
                        start_date=start_date.strftime(cls.DATE_FORMAT),
                        end_date=end_date.strftime(cls.DATE_FORMAT),
                    )
                    if not import_only and repo_group_git_repos is not None:
                        pipeline_b_and_c_result = cls.execute_pipeline_b_and_c(
                            data_dir,
                            organization=organization,
                            summary_data_dfs=contextualization_results.pipeline_a_result.summary_data_dfs,
                            repo_group_git_repos=repo_group_git_repos,
                            repo_group_jira_projects=repo_group_jira_projects,
                            jira_params=jira_params,
                            dry_run=dry_run,
                        )
                        contextualization_results.pipeline_b_and_c_result = pipeline_b_and_c_result

                if cls.PIPELINE_ANOMALY_INSIGHTS in pipelines:
                    copy_files.update(cls.COPY_FILES_PIPELINE_ANOMALY_INSIGHTS)

                    if not import_only:
                        combined_insights = cls.execute_pipeline_anomaly_insights(
                            data_dir, contextualization_results.pipeline_a_result.summary_data_dfs, dry_run=dry_run
                        )
                        contextualization_results.pipeline_anomaly_insights_result = combined_insights

                        if not dry_run and day_interval == cls.DEFAULT_DAY_INTERVAL:
                            cls.post_combined_anomaly_insights_email_to_slack(organization, day_interval=day_interval)
                            cls.post_combined_anomaly_insights_file_to_slack(organization, day_interval=day_interval)

                if cls.PIPELINE_D in pipelines:
                    jira_params = jira_params or cls.get_jira_params(
                        organization=organization,
                        start_date=start_date.strftime(cls.DATE_FORMAT),
                        end_date=end_date.strftime(cls.DATE_FORMAT),
                    )
                    if jira_params:
                        copy_files.update(cls.COPY_FILES_PIPELINE_D)

                        output_path = os.path.join(
                            data_dir,
                            cls.SCRIPT_OUTPUT_DIR,
                            cls.SCRIPT_PIPLINE_D_SUFFIX_OUTPUT_DIR,
                        )

                        if not import_only:
                            pipeline_d_result = cls.execute_pipeline_d(
                                jira_params=jira_params,
                                output_path=output_path,
                                dry_run=dry_run,
                            )
                            contextualization_results.pipeline_d_result = pipeline_d_result
                    else:
                        logger.info(
                            "Jira not connected, skipping pipeline d",
                            extra={"organization": organization.name},
                        )

                if cls.PIPELINE_JIRA_ANOMALY_INSIGHTS in pipelines:
                    jira_params = jira_params or cls.get_jira_params(
                        organization=organization,
                        start_date=start_date.strftime(cls.DATE_FORMAT),
                        end_date=end_date.strftime(cls.DATE_FORMAT),
                    )
                    if jira_params:
                        copy_files.update(cls.COPY_FILES_PIPELINE_JIRA_ANOMALY_INSIGHTS)

                        jira_anomaly_insights_output_path = os.path.join(
                            data_dir,
                            cls.SCRIPT_OUTPUT_DIR,
                            cls.SCRIPT_PIPLINE_JIRA_ANOMALY_INSIGHTS_SUFFIX_OUTPUT_DIR,
                        )

                        if not import_only:
                            jira_combined_insights = cls.execute_pipeline_jira_anomaly_insights(
                                output_path=jira_anomaly_insights_output_path,
                                contextualization_results=contextualization_results,
                                dry_run=dry_run,
                            )
                            contextualization_results.pipeline_jira_anomaly_insights_result = jira_combined_insights
                    else:
                        logger.info(
                            "Jira not connected, skipping pipeline jira anomaly insights",
                            extra={"organization": organization.name},
                        )

                if cls.PIPELINE_INSIGHTS_AGGREGATION in pipelines:
                    copy_files.update(cls.COPY_FILES_PIPELINE_INSIGHTS_AGGREGATION)

                    insights_aggregation_input_git_anomalies_file = os.path.join(
                        data_dir,
                        cls.SCRIPT_ALL_REPOS_OUTPUT_DIR,
                        cls.SCRIPT_OUTPUT_COMBINED_ANOMALY_INSIGHTS,
                    )

                    insights_aggregation_input_jira_anomalies_file = (
                        os.path.join(
                            data_dir,
                            cls.SCRIPT_OUTPUT_DIR,
                            cls.SCRIPT_PIPLINE_JIRA_ANOMALY_INSIGHTS_SUFFIX_OUTPUT_DIR,
                            cls.SCRIPT_OUTPUT_JIRA_ANOMALY_INSIGHTS_SUFFIX,
                        )
                        if jira_params
                        else None
                    )

                    if not import_only:
                        insights_aggregation = cls.execute_pipeline_insights_aggregation(
                            insights_aggregation_input_git_anomalies_file,
                            insights_aggregation_input_jira_anomalies_file,
                            contextualization_results,
                            dry_run=dry_run,
                        )
                        contextualization_results.insights_aggregation = insights_aggregation

                if not dry_run:
                    day_interval_dir = cls.create_day_interval_directory(
                        organization,
                        day_interval,
                    )
                    cls.clean_output_files(day_interval_dir)
                    cls.copy_output_files(
                        copy_files,
                        data_dir=data_dir,
                        day_interval_dir=day_interval_dir,
                        organization=organization,
                        by_group=by_group,
                    )

                    if day_interval == cls.DEFAULT_DAY_INTERVAL:
                        justification_path = os.path.join(day_interval_dir, cls.OUTPUT_FILENAME_JUSTIFICATION)
                        cls.post_justification_to_slack(organization, justification_path, start_date, end_date)

                return contextualization_results

        except Exception as e:
            logger.exception(
                "Error processing organization",
                extra={"organization": organization.name},
            )
            return None

    @staticmethod
    def get_start_and_end_date(day_interval: ContextualizationDayInterval):
        end_date = datetime.fromisoformat(settings.MOCKED_END_DATE) if settings.MOCKED_END_DATE else datetime.now()
        start_date = end_date - timedelta(days=day_interval.value)
        return start_date, end_date

    @classmethod
    def check_commits_exist_for_pipeline_a(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        """
        Checks repository commits exist for pipelines A.

        WARNING! Pipeline A should run fully before we can rely on this method for
        a contextualization window.

        This is because Pipeline A copies repositories to the __contextualization directory
        which is used to populate the __contextualization_git_data.csv file - this file is used
        to determine if commits exist.
        """
        data_dir = cls.create_contextualization_directory(organization)
        start_date, end_date = cls.get_start_and_end_date(day_interval)

        try:
            with execute_pipeline_with_telemetry("check_commits_exist_for_pipeline_a"):
                run_pipeline_a(
                    git_folder_path=data_dir,
                    start_date=start_date.strftime(cls.DATETIME_FORMAT),
                    end_date=end_date.strftime(cls.DATETIME_FORMAT),
                    run_for_commit_count=True,
                )
                return True
        except NoCommitsFoundError:
            return False

    @classmethod
    def clean_previous_data(cls, organization: Organization, pipelines: set[str]):
        """
        zip the output of the previous run and remove the directory
        removes the existing zip file if it exists
        """

        logger.info(
            f"Cleaning previous data for {organization.name} with pipelines {pipelines}",
            extra={"organization": organization.name, "pipelines": pipelines},
        )
        data_dir = cls.get_contextualization_directory(organization)
        dataset_dir = os.path.join(data_dir, cls.SCRIPT_OUTPUT_DIR)
        zip_archive = f"{dataset_dir}.zip"
        os.umask(0o002)
        # try so it doesn't crash the whole process in case there was a permission error
        try:
            if os.path.exists(zip_archive):
                os.remove(zip_archive)
            if os.path.exists(dataset_dir):
                shutil.make_archive(dataset_dir, "zip", dataset_dir)
                logger.info(
                    f"created zip archive {zip_archive}",
                    extra={"organization": organization.name},
                )
                if cls.PIPELINE_A in pipelines:
                    # TODO pipeline A deletes everything, we shouldn't do this since pipeline D doesn't need A but we'll keep it for now
                    logger.info(
                        f"deleting {dataset_dir}",
                        extra={"organization": organization.name},
                    )
                    shutil.rmtree(dataset_dir, ignore_errors=True)
                else:
                    if cls.PIPELINE_BC in pipelines:
                        # currently we only run pipeline B and C on everything so everything is inside all_repos
                        for suffix in cls.PIPLINE_BC_OUTPUT:
                            file_path = cls.get_script_output_path(data_dir, suffix)
                            if os.path.exists(file_path):
                                logger.info(
                                    f"deleting {file_path}",
                                    extra={"organization": organization.name},
                                )
                                os.remove(file_path)

                        script_output_dir = cls.get_script_output_dir(data_dir)
                        for directory in cls.PIPLINE_BC_OUTPUT_DIRECTORIES:
                            directory_path = f"{script_output_dir}/{directory}"
                            if os.path.exists(directory_path):
                                logger.info(
                                    f"deleting {directory_path}",
                                    extra={"organization": organization.name},
                                )
                                shutil.rmtree(directory_path, ignore_errors=True)

                    if cls.PIPELINE_ANOMALY_INSIGHTS in pipelines:
                        output_dir = cls.get_script_output_dir(data_dir)
                        files = os.listdir(output_dir)
                        anomaly_output_files = [
                            os.path.join(output_dir, _file)
                            for _file in files
                            if _file.endswith(tuple(cls.PIPELINE_ANOMALY_INSIGHTS_OUTPUT))
                        ]
                        for file_path in anomaly_output_files:
                            if os.path.exists(file_path):
                                logger.info(
                                    f"deleting {file_path}",
                                    extra={"organization": organization.name},
                                )
                                os.remove(file_path)

                    if cls.PIPELINE_D in pipelines:
                        output_path = os.path.join(
                            data_dir,
                            cls.SCRIPT_OUTPUT_DIR,
                            cls.SCRIPT_PIPLINE_D_SUFFIX_OUTPUT_DIR,
                        )
                        logger.info(
                            f"deleting {output_path}",
                            extra={"organization": organization.name},
                        )
                        shutil.rmtree(output_path, ignore_errors=True)

                    if cls.PIPELINE_JIRA_ANOMALY_INSIGHTS in pipelines:
                        output_path = os.path.join(
                            data_dir,
                            cls.SCRIPT_OUTPUT_DIR,
                            cls.SCRIPT_PIPLINE_JIRA_ANOMALY_INSIGHTS_SUFFIX_OUTPUT_DIR,
                        )
                        logger.info(
                            f"deleting {output_path}",
                            extra={"organization": organization.name},
                        )
                        shutil.rmtree(output_path, ignore_errors=True)

        except Exception:
            logger.exception(
                "Error cleaning previous data",
                extra={"organization": organization.name},
            )

    @classmethod
    def create_contextualization_directory(cls, organization, since=None, until=None):
        directory = cls.get_contextualization_directory(organization)
        os.makedirs(directory, exist_ok=True)

        if since and until:
            directory = os.path.join(
                directory,
                f"{since.strftime(cls.DATE_FORMAT)}_{until.strftime(cls.DATE_FORMAT)}",
            )
            os.makedirs(directory, exist_ok=True)

        return directory

    @classmethod
    def get_contextualization_directory(cls, organization):
        return os.path.join(organization.get_download_directory(), cls.DATA_DIR_NAME)

    @classmethod
    def create_day_interval_directory(
        cls,
        organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        directory = cls.get_day_interval_directory(organization, day_interval)
        os.makedirs(directory, exist_ok=True)
        return directory

    @classmethod
    def get_day_interval_directory(
        cls,
        organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        directory = cls.get_contextualization_directory(organization)
        return os.path.join(directory, cls.DAY_INTERVALS_FOLDER_MAP[day_interval.value])

    @classmethod
    def delete_symlinks(cls, data_dir):
        for path in os.listdir(data_dir):
            if os.path.islink(os.path.join(data_dir, path)):
                os.unlink(os.path.join(data_dir, path))

    @classmethod
    def create_symbolic_links(cls, organization, data_dir):
        repositories = organization.repository_set.all()
        for repository in repositories:
            path = repository.last_analysis_folder()
            if not path:
                continue

            link_path = os.path.join(data_dir, repository.public_id())

            logger.info(
                f"Creating symbolic link for {repository}: {link_path} -> {path}",
                extra={
                    "repository": repository.public_id(),
                    "organization": organization.name,
                },
            )
            os.symlink(path, link_path, target_is_directory=True)

    @classmethod
    def get_script_output_dir(cls, data_dir):
        return os.path.join(data_dir, cls.SCRIPT_ALL_REPOS_OUTPUT_DIR)

    @classmethod
    def execute_pipeline_a(
        cls,
        data_dir: str,
        start_date: datetime,
        end_date: datetime,
        repo_group_git_repos: dict[str, list[str]] = None,
        dry_run=False,
    ) -> GitAnalysisResults:
        if dry_run:
            logger.info(f"Would execute Pipeline A: {data_dir=} {start_date=} {end_date=} {repo_group_git_repos=}")
            return

        with execute_pipeline_with_telemetry("pipeline_a"):
            return run_pipeline_a(
                git_folder_path=data_dir,
                start_date=start_date.strftime(cls.DATETIME_FORMAT),
                end_date=end_date.strftime(cls.DATETIME_FORMAT),
                repo_group_git_repos=repo_group_git_repos,
            )

    @classmethod
    def execute_pipeline_a_insights(cls, git_data_path: str, dry_run=False):
        if dry_run:
            logger.info(f"Would execute Pipeline A (insights): {git_data_path=}")
            return

        with execute_pipeline_with_telemetry("pipeline_a_insights"):
            return run_pipeline_a_insights(git_data_path=git_data_path)

    @classmethod
    def execute_pipeline_b_and_c(
        cls,
        data_dir: str,
        organization: Organization,
        summary_data_dfs: dict[str, pd.DataFrame],
        repo_group_git_repos: dict[str, list[str]],
        repo_group_jira_projects: dict[str, list[str]] | None = None,
        jira_params: Optional[dict] = None,
        dry_run=False,
    ) -> PipelineBCResult | None:
        if not dry_run and not os.path.exists(data_dir):
            logger.error("data_dir not found.", extra={"data_dir": data_dir})

        if jira_params:
            jira_kwargs = {
                "jira_access_token": jira_params.get("access_token"),
                "jira_url": jira_params.get("url"),
                "start_date": jira_params.get("start_date"),
                "end_date": jira_params.get("end_date"),
            }
        else:
            logger.warning("Jira is not connected, skipping pipeline C")
            jira_kwargs = {}

        if dry_run:
            parameters_to_log = copy.deepcopy(jira_kwargs)
            if "jira_access_token" in parameters_to_log:
                parameters_to_log["jira_access_token"] = "<redacted-token>"
            logger.info(f"Would execute Pipeline B&C: {data_dir=} {parameters_to_log=}")
            return None

        with execute_pipeline_with_telemetry("pipeline_b_c"):
            pinned_initiatives_prompt = add_pinned_initiatives_input_prompt(organization=organization)
            return run_pipeline_b_c(
                data_dir=data_dir,
                summary_data_dfs=summary_data_dfs,
                repo_group_git_repos=repo_group_git_repos,
                repo_group_jira_projects=repo_group_jira_projects,
                chat_input=pinned_initiatives_prompt,
                **jira_kwargs,
            )

    @classmethod
    def execute_pipeline_anomaly_insights(
        cls, data_dir: str, summary_data_dfs: dict[str, pd.DataFrame], dry_run=False
    ) -> GitCombinedInsights | None:
        git_data_path = cls.get_script_output_path(
            data_dir,
            cls.SCRIPT_OUTPUT_SUFFIX_SUMMARY,
        )
        if not summary_data_dfs:
            raise ValueError("Pipeline A data not found. Did you run pipeline A?")
        if dry_run:
            logger.info(f"Would execute Pipeline Anomaly Insights: {git_data_path=} {data_dir=}")
            return None

        with execute_pipeline_with_telemetry("anomaly_insights"):
            return run_anomaly_driven_insights(
                git_data_path=git_data_path,
                git_repo_path=data_dir,
                summary_data_df=list(summary_data_dfs.values())[0],
            )

    @classmethod
    def execute_pipeline_insights_aggregation(
        cls,
        git_anomaly_file: str,
        jira_anomaly_file: str | None,
        contextualization_results: ContextualizationResults,
        dry_run=False,
    ):
        if not dry_run and not os.path.exists(git_anomaly_file):
            error_message = "'git_anomaly_file' not found. Did you run pipeline anomaly_insights?"
            logger.error(error_message, extra={"git_anomaly_file": git_anomaly_file})
            raise FileNotFoundError(error_message)

        files = [git_anomaly_file]

        if jira_anomaly_file:
            if not dry_run and not os.path.exists(jira_anomaly_file):
                error_message = "'jira_anomaly_file' not found. Did you run pipeline jira_anomaly_insights?"
                logger.error(error_message, extra={"jira_anomaly_file": jira_anomaly_file})
                raise FileNotFoundError(error_message)

            files.append(jira_anomaly_file)

        if dry_run:
            logger.info(f"Would execute Pipeline Insights Aggregation: {files=}")
            return None

        with execute_pipeline_with_telemetry("pipeline_insights_aggregation"):
            return run_insights_aggregation_pipeline(
                input_files=files, contextualization_results=contextualization_results
            )

    @classmethod
    def execute_pipeline_d(cls, jira_params: dict, output_path: str, dry_run=False) -> PipelineDResult | None:
        if not jira_params:
            logger.info("Jira not connected, skipping pipeline d")
            return None

        if dry_run:
            parameters_to_log = copy.deepcopy(jira_params)
            if "jira_access_token" in parameters_to_log:
                parameters_to_log["jira_access_token"] = "<redacted-token>"
            logger.info(f"Would execute Pipeline D: {parameters_to_log=} {output_path=}")
            return None

        with execute_pipeline_with_telemetry("pipeline_d"):
            result = run_jira_completeness_score_pipeline(
                jira_project_names=jira_params.get("projects_keys", []),
                output_path=output_path,
                jira_url=jira_params.get("url"),
                confluence_user=jira_params.get("confluence_user"),
                jira_access_token=jira_params.get("access_token"),
                start_date=jira_params.get("start_date"),
                end_date=jira_params.get("end_date"),
            )

        return result

    @classmethod
    def execute_pipeline_jira_anomaly_insights(
        cls, output_path: str, contextualization_results: ContextualizationResults, dry_run=False
    ) -> JiraCombinedInsights | None:
        if dry_run:
            logger.info(f"Would execute Pipeline Jira Anomaly Insights: {output_path=}")
            return None

        with execute_pipeline_with_telemetry("pipeline_jira_anomaly_insights"):
            if contextualization_results.pipeline_d_result is None:
                logger.warning("Pipeline D result not found. Did you run pipeline D?")
                return None

            return run_jira_anomaly_driven_insights_pipeline(
                output_path=output_path,
                jira_data_df=contextualization_results.pipeline_d_result.jira_data_df,
            )

    @classmethod
    def clean_output_files(cls, day_interval_dir: str):
        logger.info(f"Cleaning output files for directory {day_interval_dir}")
        for filename in os.listdir(day_interval_dir):
            file_path = os.path.join(day_interval_dir, filename)
            if os.path.isfile(file_path):
                logger.info(f"Deleting {file_path}")
                os.unlink(file_path)

    @classmethod
    def copy_output_files(
        cls,
        files,
        data_dir: str,
        day_interval_dir: str,
        organization: Organization,
        by_group=False,
    ):
        output_dir = os.path.join(data_dir, day_interval_dir)
        logger.info(
            f"Copying output files to {output_dir}",
            extra={"organization": organization.name},
        )
        if by_group:
            cls.combine_git_data_overall_summary_final(data_dir, output_dir, organization)

        for suffix, destination_filename in files.items():
            script_output_path = cls.get_script_output_path(data_dir, suffix)

            if not os.path.exists(script_output_path):
                raise FileNotFoundError(f"Script output file not found: {script_output_path}")

            output_path = os.path.join(output_dir, destination_filename)
            shutil.copy(script_output_path, output_path)

    @classmethod
    def get_script_output_path(cls, data_dir: str, suffix: str):
        # TODO this is very hacky, need to be fixed

        if suffix == cls.SCRIPT_OUTPUT_JIRA_DATA_WITH_SCORE_SUMMARY_SUFFIX:
            output_dir = os.path.join(data_dir, cls.SCRIPT_OUTPUT_DIR, cls.SCRIPT_PIPLINE_D_SUFFIX_OUTPUT_DIR)
        elif suffix == cls.SCRIPT_OUTPUT_JIRA_DATA_WITH_QUALITY_SUMMARY_SUFFIX:
            output_dir = os.path.join(data_dir, cls.SCRIPT_OUTPUT_DIR, cls.SCRIPT_PIPLINE_D_SUFFIX_OUTPUT_DIR)
        elif suffix == cls.SCRIPT_OUTPUT_JIRA_ANOMALY_INSIGHTS_SUFFIX:
            output_dir = os.path.join(
                data_dir,
                cls.SCRIPT_OUTPUT_DIR,
                cls.SCRIPT_PIPLINE_JIRA_ANOMALY_INSIGHTS_SUFFIX_OUTPUT_DIR,
            )
        else:
            output_dir = cls.get_script_output_dir(data_dir)

        if suffix == cls.SCRIPT_OUTPUT_COMBINED_ANOMALY_INSIGHTS:
            filename = suffix
        elif suffix == cls.SCRIPT_OUTPUT_INSIGHTS_AGGREGATION:
            filename = suffix
        elif suffix == cls.SCRIPT_OUTPUT_JIRA_DATA_WITH_SCORE_SUMMARY_SUFFIX:
            filename = suffix
        elif suffix == cls.SCRIPT_OUTPUT_JIRA_DATA_WITH_QUALITY_SUMMARY_SUFFIX:
            filename = suffix
        elif suffix == cls.SCRIPT_OUTPUT_JIRA_ANOMALY_INSIGHTS_SUFFIX:
            filename = suffix
        else:
            filename = f"{cls.DATA_DIR_NAME}{suffix}"

        return os.path.join(output_dir, filename)

    # NOTE: main_insights.py uses a different output folder
    # TODO: normalize this
    @classmethod
    def get_insights_output_path(cls, data_dir: str, suffix: str):
        filename = f"{cls.DATA_DIR_NAME}{suffix}".replace("_git_data_", "_git_data.csv_")
        return os.path.join(data_dir, filename)

    @classmethod
    def read_combined_anomaly_script_output(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        day_interval_dir = cls.get_day_interval_directory(organization, day_interval)
        path = os.path.join(
            day_interval_dir,
            cls.OUTPUT_FILENAME_COMBINED_ANOMALY_INSIGHTS,
        )
        if not os.path.exists(path):
            logger.error(
                f"Combined anomalies insights file not found",
                extra={"organization": organization.name, "path": path},
            )
            with push_scope() as scope:
                scope.set_extra("organization", organization.name)
                scope.set_extra("combined_anomaly_script_output_path", path)
                traceback_on_debug()
                capture_message("Combined anomalies insights file not found")

            return None

        with open(path) as f:
            return json.load(f)

    @classmethod
    def get_organizations(
        cls, organization_ids: Optional[list[int]] = None, skip_organization_ids: Optional[list[int]] = None
    ):
        qs = Organization.objects

        if organization_ids:
            qs = qs.filter(id__in=organization_ids)

        if skip_organization_ids:
            logger.warning(
                f"Skipping contextualisation for organisations {skip_organization_ids}",
                extra={"skipped_organization_ids": skip_organization_ids},
            )
            qs = qs.exclude(id__in=skip_organization_ids)

        return qs.filter(contextualization_enabled=True)

    @classmethod
    def get_jira_params(cls, organization: Organization, start_date: str, end_date: str) -> dict | None:
        """
        Returns Jira parameters for the organization if Jira is connected.

        Args:
            organization: The organization for which Jira parameters are retrieved.
            start_date: The start date in "YYYY-MM-DD" format.
            end_date: The end date in "YYYY-MM-DD" format.
        """
        jira_connection = DataProviderConnection.objects.filter(
            organization=organization, provider=JiraIntegration().provider
        ).first()

        if not jira_connection or not JiraIntegration.is_connection_connected(jira_connection):
            return None

        cloud_id = jira_connection.data.get("cloud_id")

        integration = JiraIntegration()
        integration.init_api(
            config=JiraApiConfig(
                access_token=jira_connection.data.get("access_token"),
                refresh_token=jira_connection.data.get("refresh_token"),
                cloud_id=cloud_id,
            ),
            connection=jira_connection,
        )
        api = integration.api

        selected_projects = JiraProject.objects.filter(organization=organization, is_selected=True).values_list(
            "key", flat=True
        )

        projects = api.get_projects()
        projects_keys = [project["key"] for project in projects if project.get("key") in selected_projects]
        if not projects_keys:
            logging.info("No Jira project selected.", extra={"organization": organization.name})
            return None

        return {
            "access_token": api.access_token,
            "url": f"{JiraApi.API_BASE_URL}/ex/jira/{cloud_id}",
            "start_date": start_date,
            "end_date": end_date,
            "projects_keys": projects_keys,
        }

    @classmethod
    def format_combined_anomaly_script_output_for_email(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        data = cls.read_combined_anomaly_script_output(organization, day_interval)
        if not data:
            return None

        anomaly_insights = data.get("anomaly_insights")
        if not anomaly_insights:
            error_message = "Anomaly insights not found in JSON"
            logger.error(error_message, extra={"organization": organization.name})
            with push_scope() as scope:
                scope.set_extra("combined_anomaly_script_output", data)
                scope.set_extra("organization", organization.name)
                traceback_on_debug()
                capture_message(error_message)

            return None

        valid_repositories = (
            cls.get_repositories_by_lookback_hours(organization)
            if cls.ANOMALY_INSIGHTS_REPO_LOOKBACK_HOURS
            else organization.repository_set.all()
        )
        valid_repository_public_ids = [repo.public_id() for repo in valid_repositories]
        valid_repository_map = {repo.public_id(): repo.full_name() for repo in valid_repositories}
        filtered_anomaly_insights = [
            {"repo_name": valid_repository_map[anomaly["repo"]], **anomaly}
            for anomaly in anomaly_insights
            if anomaly["repo"] in valid_repository_public_ids
        ]
        if not filtered_anomaly_insights:
            logger.info(
                f"Anomaly insights not found after filtering for organization: {organization.name}",
                extra={"organization": organization.name},
            )
            return None

        email_content = textwrap.dedent(
            f"""
            Here are up to five anomaly insights since the last business day.
            Want to see more? Login: {cls.ANOMALY_INSIGHTS_EMAIL_LINK}.
            """
        )
        for anomaly in filtered_anomaly_insights[: cls.ANOMALY_INSIGHTS_PER_EMAIL]:
            email_content += textwrap.dedent(
                f"""
                Repository: {anomaly["repo_name"]}:
                Overview: {anomaly["insight"]}
                Detail: {anomaly["evidence"]}
                """
            )

        return email_content

    @classmethod
    def get_repositories_by_lookback_hours(cls, organization: Organization):
        end_date = timezone.now()
        start_date = end_date - timedelta(hours=cls.ANOMALY_INSIGHTS_REPO_LOOKBACK_HOURS)
        return organization.repository_set.filter(updated_at__range=[start_date, end_date])

    @classmethod
    def post_combined_anomaly_insights_file_to_slack(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        # TODO: Could this be moved to a SlackIntegration class?
        # TODO: use a flag instead
        if str(organization.pk) not in settings.SLACK_WEBHOOK_ORGANIZATIONS:
            return

        data = cls.read_combined_anomaly_script_output(organization, day_interval)
        if not data:
            return

        raw_data = json.dumps(data, indent=2)
        is_truncated = len(raw_data) > SlackIntegration.MAX_MESSAGE_LENGTH
        raw_truncated_data = raw_data[: SlackIntegration.MAX_MESSAGE_LENGTH - SlackIntegration.MESSAGE_SAFETY_MARGIN]
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": (f"Combined Anomaly Insights file for Organization: {organization.name}"),
                },
            },
            {"type": "divider"},
            SlackIntegration.get_markdown_block(
                f"\n```{raw_truncated_data}\n{is_truncated and '... (truncated)' or ''}```"
            ),
        ]
        SlackIntegration.send_webhook(settings.SLACK_WEBHOOK_URL, blocks)

    @classmethod
    def post_combined_anomaly_insights_email_to_slack(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        # TODO: Could this be moved to a SlackIntegration class?
        # TODO: use a flag instead
        if str(organization.pk) not in settings.SLACK_WEBHOOK_ORGANIZATIONS:
            return

        email = cls.format_combined_anomaly_script_output_for_email(organization, day_interval)
        if not email:
            return

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": (f"Combined Anomaly Insights email for Organization: {organization.name}"),
                },
            },
            {"type": "divider"},
            SlackIntegration.get_markdown_block(f"```{email}```"),
        ]
        SlackIntegration.send_webhook(settings.SLACK_WEBHOOK_URL, blocks)

    @classmethod
    def post_justification_to_slack(
        cls,
        organization: Organization,
        justification_path: str,
        start_date: datetime,
        end_date: datetime,
    ):
        # TODO: Could this be moved to a SlackIntegration class?
        # TODO: use a flag instead
        if str(organization.pk) not in settings.SLACK_WEBHOOK_ORGANIZATIONS:
            return

        justification = json.load(open(justification_path))
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Justification for Organization: {organization.name}",
                },
            },
            SlackIntegration.get_markdown_block(
                "\n".join(
                    [
                        f"From: {start_date.strftime(cls.DATE_SLACK_FORMAT)}",
                        f"To:  {end_date.strftime(cls.DATE_SLACK_FORMAT)}",
                        f"Organization: {organization.name}",
                        "",
                        "*INSIGHTS SUMMARY:*",
                        justification.get("summary"),
                    ]
                )
            ),
        ]
        for category_key, category in justification.get("categories", []).items():
            category_name = category_key.replace("_", " ").upper()
            blocks.extend(
                [
                    {"type": "divider"},
                    SlackIntegration.get_markdown_block(f"*{category_name}* ({category.get('percentage')}%)"),
                    SlackIntegration.get_quote_block("Justification", category.get("justification")),
                    SlackIntegration.get_quote_block("Examples", category.get("examples")),
                ]
            )

        # TODO: get webhook from organization settings
        SlackIntegration.send_webhook(settings.SLACK_WEBHOOK_URL, blocks)

    @classmethod
    def format_justification_for_email(
        cls,
        organization: Organization,
        start_date: datetime,
        end_date: datetime,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        day_interval_dir = cls.get_day_interval_directory(organization, day_interval)
        justification_path = os.path.join(day_interval_dir, cls.OUTPUT_FILENAME_JUSTIFICATION)
        if not os.path.exists(justification_path):
            error_message = "Justification file not found"
            logger.error(error_message, extra={"organization": organization.name})
            with push_scope() as scope:
                scope.set_extra("organization", organization.name)
                scope.set_extra("justification_path", justification_path)
                traceback_on_debug()
                capture_message(error_message)

            return None

        with open(justification_path) as f:
            justification = json.load(f)

        email_content = textwrap.dedent(
            f"""
            From: {start_date.strftime(cls.DATE_FORMAT)}
            To:  {end_date.strftime(cls.DATE_FORMAT)}
            Organization: {organization.name}

            "INSIGHTS SUMMARY:",
            {justification.get("summary")}
            """
        )

        for category_key, category in justification.get("categories", []).items():
            category_name = category_key.replace("_", " ").upper()
            email_content += textwrap.dedent(
                f"""
                {category_name} ({category.get("percentage")}%)
                Justification: {category.get("justification")}

                Examples: {category.get("examples")}
                """
            )

        return email_content

    @classmethod
    def get_output_file_path(
        cls,
        organization: Organization,
        filename: str,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        day_interval_dir = cls.get_day_interval_directory(organization, day_interval)
        return os.path.join(
            organization.get_download_directory(),
            cls.DATA_DIR_NAME,
            day_interval_dir,
            filename,
        )

    @classmethod
    def load_output_data(
        cls,
        organization: Organization,
        filename: str,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        file_path = cls.get_output_file_path(organization, filename, day_interval)
        if not os.path.exists(file_path):
            return {}, 0

        try:
            data = json.load(open(file_path))
            file_timestamp = os.path.getmtime(file_path)
            return data, file_timestamp
        except FileNotFoundError as error:
            logger.exception(
                "Error loading output data",
                extra={"file_path": file_path, "organization": organization.name},
            )
            with push_scope() as scope:
                scope.set_extra("file_path", file_path)
                traceback_on_debug()
                capture_exception(error)

            return {}, 0

    @classmethod
    def get_output_data_timestamp(
        cls,
        organization: Organization,
        filename: str,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        file_path = cls.get_output_file_path(organization, filename, day_interval)
        if not os.path.exists(file_path):
            return 0

        return os.path.getmtime(file_path)

    @classmethod
    def load_output_csv(
        cls,
        organization: Organization,
        filename: str,
        day_interval: ContextualizationDayInterval = DEFAULT_DAY_INTERVAL,
    ):
        file_path = cls.get_output_file_path(organization, filename, day_interval)
        if not os.path.exists(file_path):
            return None

        try:
            data = json.load(open(file_path))
            file_timestamp = os.path.getmtime(file_path)
            return data, file_timestamp
        except FileNotFoundError as error:
            logger.exception(
                "Error loading output CSV",
                extra={"file_path": file_path, "organization": organization.name},
            )
            with push_scope() as scope:
                scope.set_extra("file_path", file_path)
                traceback_on_debug()
                capture_exception(error)

            return {}, 0

    @classmethod
    def process_project_information_chat_input(cls, organization: Organization):
        cls.clean_previous_data(organization, pipelines={cls.PIPELINE_BC})
        data_dir = cls.create_contextualization_directory(organization)

    @classmethod
    def generate_repository_group(cls, organization: Organization) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        repo_groups = RepositoryGroup.objects.filter(organization=organization).order_by("name")

        repo_group_git_repos = {}
        repo_group_jira_projects = {}
        for repo_group in repo_groups:
            group_name = repo_group.public_id()

            # Jira
            jira_projects = JiraProject.objects.filter(repository_group=repo_group).all()
            repo_group_jira_projects[group_name] = [project.name for project in jira_projects]

            # Git
            repositories = Repository.objects.filter(group=repo_group).all()
            repo_group_git_repos[group_name] = [repo.public_id() for repo in repositories]

        return repo_group_git_repos, repo_group_jira_projects

    @classmethod
    def generate_summary_csv(cls, organization: Organization, since, until):
        records = GitDiffContext.objects.filter(
            repository__organization=organization,
            time__gte=since,
            time__lte=until,
        ).prefetch_related("repository")

        data_dir = cls.create_contextualization_directory(organization, since, until)
        filepath = os.path.join(data_dir, f"{cls.DATA_DIR_NAME}{cls.SCRIPT_OUTPUT_SUFFIX_SUMMARY}")

        with open(filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "repository",
                    "id",
                    "date",
                    "files",
                    "Summary",
                    "Categorization_of_Changes",
                    "Maintenance_Relevance",
                    "Description_of_Maintenance_Relevance",
                    "Purpose_of_change",
                    "Impact_on_product",
                ]
            )

            for record in records:
                writer.writerow(
                    [
                        record.repository.public_id(),
                        record.sha,
                        record.time,
                        record.file_path,
                        record.summary,
                        record.category,
                        record.maintenance_relevance,
                        record.description_of_maintenance_relevance,
                        record.purpose_of_change,
                        record.impact_on_product,
                    ]
                )

        return filepath

    @classmethod
    def combine_git_data_overall_summary_final(cls, data_dir, output_dir, organization: Organization):
        logger.info(
            "Combining git data overall summary final",
            extra={"organization": organization.name},
        )
        combined_file_path = os.path.join(output_dir, cls.OUTPUT_FILENAME_GROUPED_JUSTIFICATION)
        groups_ids = [group.public_id() for group in organization.repositorygroup_set.all()] + [cls.UNGROUPED_LABEL]
        os.makedirs(os.path.dirname(combined_file_path), exist_ok=True)

        combined_data = {}
        for group_id in groups_ids:
            file_path = f"{data_dir}/{cls.SCRIPT_OUTPUT_DIR}/{group_id}/{cls.DATA_DIR_NAME}{cls.SCRIPT_OUTPUT_SUFFIX_SUMMARY_FINAL}"
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    data = json.load(f)
                    combined_data[group_id] = data

        with open(combined_file_path, "w") as output_file:
            json.dump(combined_data, output_file, indent=4)

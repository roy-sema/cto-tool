import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, cast

from django.utils import timezone

from compass.dashboard.models import GitDiffContext, GitDiffRepositoryGroupInsight
from mvp.models import Organization
from mvp.services.contextualization_service import ContextualizationService
from mvp.utils import process_csv_file

logger = logging.getLogger(__name__)


class ImportContextualizationDataTask:
    CSV_DELIMITER = ","

    def __init__(self):
        self.organization = None
        self.repositories = None
        self.repository_id_map = {}

    def run(self, organization: Organization):
        self.organization = organization
        self.repositories = organization.repository_set.all()

        if not self.repositories:
            logger.info("No repositories found")
            return False

        self.repository_id_map = {repo.public_id(): repo for repo in self.repositories}

        return self.import_data_to_db(organization)

    def import_data_to_db(self, organization):
        summary_imported = self.import_summary_data(organization)
        justification_imported = self.import_justification_data(organization)
        return all([summary_imported, justification_imported])

    def import_summary_data(self, organization):
        data_dir = ContextualizationService.create_contextualization_directory(organization)

        csv_path = ContextualizationService.get_script_output_path(
            data_dir, ContextualizationService.SCRIPT_OUTPUT_SUFFIX_SUMMARY
        )

        if not csv_path or not os.path.exists(csv_path):
            logger.info("No summary file found")
            return False

        process_csv_file(
            csv_path,
            self.process_summary_row,
            delimiter=self.CSV_DELIMITER,
        )

        return True

    def process_summary_row(self, row):
        repo_public_id = row.get("repository")
        commit_sha = row.get("id")
        date = row.get("date")
        file_path = row.get("files")
        git_diff = row.get("code")
        category = row.get("Categorization_of_Changes")
        summary = row.get("Summary")
        maintenance_relevance = row.get("Maintenance_Relevance")
        description_of_maintenance_relevance = row.get("Description_of_Maintenance_Relevance")
        impact_on_product = row.get("Impact_on_product")
        purpose_of_change = row.get("Purpose_of_change")

        if not repo_public_id or not commit_sha or not date or not file_path:
            logger.warning(f"Missing required fields in row: {row}. Skipping import for this row.")
            return False

        if repo_public_id not in self.repository_id_map:
            logger.warning(f"Repository with public ID {repo_public_id} not found. Skipping import for this row.")
            return False

        repository = self.repository_id_map[repo_public_id]

        git_diff_hash = hashlib.sha256(git_diff.encode("utf-8")).hexdigest()
        _time = timezone.make_aware(datetime.strptime(date, "%Y-%m-%d"))

        GitDiffContext.objects.update_or_create(
            repository=repository,
            sha=commit_sha,
            file_path=file_path[:500],
            git_diff_hash=git_diff_hash,
            time=_time,
            defaults={
                "category": category,
                "summary": summary,
                "maintenance_relevance": maintenance_relevance,
                "description_of_maintenance_relevance": description_of_maintenance_relevance,
                "impact_on_product": impact_on_product,
                "purpose_of_change": purpose_of_change,
            },
        )

        return True

    def import_justification_data(
        self,
        organization,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        data: dict[str, Any] | None = None,
    ):
        data_dir = ContextualizationService.create_contextualization_directory(organization, since, until)

        json_path = (
            ContextualizationService.get_insights_output_path(
                data_dir, ContextualizationService.SCRIPT_OUTPUT_SUFFIX_SUMMARY_FINAL
            )
            if since and until
            else ContextualizationService.get_script_output_path(
                data_dir, ContextualizationService.SCRIPT_OUTPUT_SUFFIX_SUMMARY_FINAL
            )
        )
        if not data:
            if not json_path or not os.path.exists(json_path):
                logger.info("No justification file found")
                return False
            data = cast(dict[str, Any], json.loads(Path(json_path).read_text()))

        if not since or not until:
            until = datetime.now()
            since = until - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value)

        categories = data.get("categories", [])
        for category, insight in categories.items():
            GitDiffRepositoryGroupInsight.objects.update_or_create(
                organization=organization,
                # TODO: grouped_justification should set this. What about "other"?
                repository_group=None,
                start_date=since,
                end_date=until,
                category=category,
                defaults={
                    "percentage": insight.get("percentage"),
                    "justification": insight.get("justification"),
                    "examples": insight.get("examples"),
                    "generated": True,
                },
            )

        return True

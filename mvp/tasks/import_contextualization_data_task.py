import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from compass.dashboard.models import GitDiffContext, GitDiffRepositoryGroupInsight
from mvp.mixins import DecodePublicIdMixin
from mvp.models import Organization, RepositoryGroup
from mvp.services.contextualization_service import ContextualizationResults, ContextualizationService

logger = logging.getLogger(__name__)


class ImportContextualizationDataTask:
    CSV_DELIMITER = ","

    def __init__(self, organization: Organization, pipeline_results: ContextualizationResults):
        self.organization = organization
        self.repositories = None
        self.repository_id_map = {}
        self.pipeline_results = pipeline_results

    def run(self):
        self.repositories = self.organization.repository_set.all()

        if not self.repositories:
            logger.info("No repositories found")
            return False

        self.repository_id_map = {repo.public_id(): repo for repo in self.repositories}

        return self.import_data_to_db()

    def import_data_to_db(self):
        for row in self.pipeline_results.pipeline_a_result.summary_data_all_repos.commits:
            self.process_summary_row(row.model_dump())
        justification_imported = self.import_justification_data(self.organization)
        return all([True, justification_imported])

    def process_summary_row(self, row):
        repo_public_id = row.get("repository")
        commit_sha = row.get("id")
        date = row.get("date")
        file_path = row.get("files")
        git_diff = row.get("code")
        category = row.get("category")
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

        GitDiffContext.objects.update_or_create(
            repository=repository,
            sha=commit_sha,
            file_path=str(file_path)[:500],
            git_diff_hash=git_diff_hash,
            time=date,
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
    ):
        if not since or not until:
            until = datetime.now()
            since = until - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value)

        activity = self.pipeline_results.pipeline_a_result.development_activity_by_repo
        for repo_group_id, activity_justifications in activity.items():
            if repo_group_id == "all_repos":
                repository_group = None
            else:
                decoded_id = DecodePublicIdMixin.decode_id(repo_group_id)
                repository_group = RepositoryGroup.objects.filter(id=decoded_id).first()

            for activity_justification in activity_justifications:
                category = activity_justification.activity_type.value.replace("_", " ").capitalize()
                GitDiffRepositoryGroupInsight.objects.update_or_create(
                    organization=organization,
                    repository_group=repository_group,
                    start_date=since,
                    end_date=until,
                    category=category,
                    defaults={
                        "justification": activity_justification.justification,
                        "generated": True,
                    },
                )

        return True

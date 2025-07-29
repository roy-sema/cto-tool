import logging
import os
from datetime import datetime, timedelta

from django.db import transaction

from compass.contextualization.models import (
    Initiative,
    InitiativeEpic,
    ReconcilableInitiative,
    Roadmap,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import PipelineBCResult
from mvp.models import Organization, RepositoryGroup
from mvp.services import ContextualizationDayInterval, ContextualizationService
from mvp.services.initiatives_service import get_pinned_initiatives

logger = logging.getLogger(__name__)


class ImportPipelineBCDataTask:
    def import_results(
        self, organization: Organization, day_interval: ContextualizationDayInterval, result: PipelineBCResult
    ):
        logger.info(f"Importing pipeline bc data for {organization}")
        repo_groups = RepositoryGroup.objects.filter(organization=organization).order_by("name")
        for repository_group in repo_groups:
            logger.info(f"Importing repo group {repository_group}")

            public_id = repository_group.public_id()
            result_item = result.items.get(public_id)
            if not result_item:
                logger.warning("No item for repository group with identifier %s", public_id)
                continue
            roadmap_data = result_item.git_initiatives.dict() if result_item else {}
            roadmap_updated_at = self.get_group_file_timestamp(
                organization,
                repository_group,
                ContextualizationService.SCRIPT_OUTPUT_SUFFIX_GIT_INITIATIVES_COMBINED,
            )

            reconciliation_roadmap_data = result_item.insights.dict() if result_item and result_item.insights else None
            reconciliation_updated_at = self.get_group_file_timestamp(
                organization,
                repository_group,
                ContextualizationService.SCRIPT_OUTPUT_SUFFIX_RECONCILIATION_INSIGHTS,
            )

            updated_ats = [roadmap_updated_at, reconciliation_updated_at]
            updated_ats = [time for time in updated_ats if time]
            if not updated_ats:
                logger.info(f"There is no data for {repository_group=}. Skipping.")
                continue

            updated_at = min(updated_ats) if updated_ats else 0

            end_date = datetime.fromtimestamp(updated_at).date()
            start_date = (datetime.fromtimestamp(updated_at) - timedelta(days=day_interval.value)).date()

            with transaction.atomic():
                pinned_initiatives = get_pinned_initiatives(organization)
                roadmap = Roadmap.objects.create(
                    summary=roadmap_data.get("summary"),
                    start_date=start_date,
                    end_date=end_date,
                    day_interval=day_interval.value,
                    organization=organization,
                    repository_group=repository_group,
                    raw_roadmap=roadmap_data,
                    raw_roadmap_reconciliation=reconciliation_roadmap_data,
                )
                logger.info("Created roadmap")

                self.save_initiatives(roadmap, roadmap_data, pinned_initiatives)
                logger.info("Saved initiatives")
                if reconciliation_roadmap_data:
                    self.save_reconcilable_initiatives(roadmap, reconciliation_roadmap_data)
                logger.info("Saved reconcilable initiatives")
            logger.info(f"Imported data for {repository_group}")

        logger.info(f"Imported pipeline bc data for {organization}")

    @staticmethod
    def get_group_file_timestamp(organization: Organization, group: RepositoryGroup, file_name: str) -> float:
        file_path = os.path.join(
            ContextualizationService.get_contextualization_directory(organization),
            ContextualizationService.SCRIPT_OUTPUT_DIR,
            group.public_id(),
            ContextualizationService.DATA_DIR_NAME + file_name,
        )
        if not os.path.exists(file_path):
            return 0

        return os.path.getmtime(file_path)

    def save_initiatives(self, roadmap: Roadmap, data: dict, pinned_initiatives: list[Initiative]):
        pinned_names = {init.name: init for init in pinned_initiatives}
        pinned_custom_names = {init.custom_name: init for init in pinned_initiatives}

        initiatives = []

        for item in data.get("initiatives", []):
            estimated_end_date = None
            delivery_estimate = item.get("delivery_estimate")
            if delivery_estimate:
                estimated_end_date = delivery_estimate.get("executive_summary", {}).get("estimated_completion_date")

            initiative_name = item.get("initiative_name")
            matched_initiative = self.match_initiative_by_name(initiative_name, pinned_names, pinned_custom_names)

            initiative = Initiative.objects.create(
                name=initiative_name,
                justification=item.get("initiative_description"),
                percentage=item.get("initiative_percentage"),
                percentage_tickets_done=item.get("percentage_tickets_done") or 0,
                tickets_done=item.get("number_ticket_done") or 0,
                tickets_total=item.get("total_tickets") or 0,
                start_date=item.get("start_date"),
                estimated_end_date=estimated_end_date,
                delivery_estimate=delivery_estimate,
                roadmap=roadmap,
                pinned=matched_initiative.pinned if matched_initiative else False,
                parent=matched_initiative,
            )

            if matched_initiative:
                pinned_epics = matched_initiative.epics.all()
                pinned_epic_names = {e.name: e for e in pinned_epics}
                pinned_epic_custom_names = {e.custom_name: e for e in pinned_epics if e.custom_name}
            else:
                pinned_epic_names = {}
                pinned_epic_custom_names = {}

            for epic in item.get("epics", []):
                epic_name = epic.get("epic_name")
                matched_epic = self.match_initiative_by_name(epic_name, pinned_epic_names, pinned_epic_custom_names)

                InitiativeEpic.objects.create(
                    name=epic_name,
                    description=epic.get("epic_description"),
                    percentage=epic.get("epic_percentage", 0),
                    initiative=initiative,
                    pinned=matched_epic.pinned if matched_epic else False,
                    parent=matched_epic,
                )

            initiatives.append(initiative)

        return initiatives

    @staticmethod
    def match_initiative_by_name(
        initiative_name: str,
        pinned_names: dict[str, Initiative | InitiativeEpic],
        pinned_custom_names: dict[str, Initiative | InitiativeEpic],
    ) -> Initiative | InitiativeEpic | None:
        if initiative := pinned_custom_names.get(initiative_name):
            logger.info(
                f"Matching {'Initiative' if isinstance(initiative, Initiative) else 'Epic'} `{initiative_name}`"
            )
            return initiative
        if initiative := pinned_names.get(initiative_name):
            logger.info(
                f"Matching {'Initiative' if isinstance(initiative, Initiative) else 'Epic'} `{initiative_name}`"
            )
            return initiative
        return None

    @staticmethod
    def save_reconcilable_initiatives(roadmap: Roadmap, data: dict):
        reconcilable_initiatives = []
        for item in data.get("insights", []):
            # ignore items that don't need reconciliation
            if not item.get("needs_reconciliation"):
                continue

            ReconcilableInitiative.objects.create(
                name=item.get("work_group"),
                initiative_type=item.get("work_group_type"),
                git_activity=item.get("git_activity"),
                jira_activity=item.get("jira_activity"),
                roadmap=roadmap,
            )
        return reconcilable_initiatives

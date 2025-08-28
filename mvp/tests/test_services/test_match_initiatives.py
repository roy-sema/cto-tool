from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from compass.contextualization.models import Initiative, InitiativeEpic, Roadmap
from compass.contextualization.tasks.import_pipeline_bc_data_task import ImportPipelineBCDataTask
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import (
    AccelerationSummary,
    GitInitiatives,
    InitiativeAccelerations,
    PipelineBCResult,
    PipelineBCResultItem,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import (
    Epic as SchemaEpic,
)
from contextualization.pipelines.pipeline_B_and_C_product_roadmap.schemas import (
    Initiative as SchemaInitiative,
)
from mvp.models import Organization, RepositoryGroup
from mvp.services import ContextualizationDayInterval


class ImportPipelineBCDataTaskTest(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="TestOrg")
        self.repo_group = RepositoryGroup.objects.create(name="TestRepoGroup", organization=self.organization)

        # Existing pinned initiative
        self.existing_pinned_initiative = Initiative.objects.create(
            name="Existing Initiative",
            custom_name="Pinned Custom Name",
            pinned=True,
            roadmap=Roadmap.objects.create(
                organization=self.organization,
                start_date="2024-01-01",
                end_date="2024-01-15",
                day_interval=14,
            ),
        )

        # Matching pinned epic by name
        self.existing_pinned_epic = InitiativeEpic.objects.create(
            name="Epic 1",
            pinned=True,
            initiative=self.existing_pinned_initiative,
        )

        # Matching pinned epic by custom_name (for the custom name test)
        self.existing_pinned_epic_with_custom_name = InitiativeEpic.objects.create(
            name="Non-Matching Name",
            custom_name="Pinned Epic Custom",
            pinned=True,
            initiative=self.existing_pinned_initiative,
        )

    def create_test_result(self, initiatives_data):
        """Create a test result for the pipeline's business context evaluation.

        This method generates a `PipelineBCResult` object, which contains detailed
        information about the initiatives, acceleration summaries, and other relevant
        factors pertaining to the pipeline. The result includes structured data for
        further processing or display.
        """
        return PipelineBCResult(
            items={
                self.repo_group.public_id(): PipelineBCResultItem(
                    git_initiatives=GitInitiatives(
                        summary="Roadmap summary",
                        initiatives=initiatives_data,
                    ),
                    acceleration_summary=AccelerationSummary(
                        universal_strategies=["Strategy 1"],
                        key_changes_needed=["Key change 1"],
                        result="Strategy 1 and Key change 1",
                        initiative_accelerations=[InitiativeAccelerations(name="Speed up", increase_weeks=2)],
                    ),
                )
            }
        )

    @patch.object(ImportPipelineBCDataTask, "get_group_file_timestamp")
    def test_import_matching_by_initiative_name(self, mock_get_group_file_timestamp):
        """Test imported initiative matches pinned and is marked as pinned."""
        mock_get_group_file_timestamp.return_value = timezone.now().timestamp()

        result = self.create_test_result(
            [
                SchemaInitiative(
                    initiative_name="Existing Initiative",
                    initiative_description="Test desc",
                    initiative_percentage=50,
                    epics=[
                        SchemaEpic(
                            epic_name="Epic 1",
                            epic_description="Epic desc",
                            epic_percentage=100,
                        )
                    ],
                )
            ]
        )

        task = ImportPipelineBCDataTask()
        task.import_results(self.organization, ContextualizationDayInterval.TWO_WEEKS, result)

        roadmap = Roadmap.latest_by_org(self.organization)
        initiative = Initiative.objects.get(name="Existing Initiative", roadmap=roadmap)
        InitiativeEpic.objects.get(name="Epic 1", initiative=initiative)
        self.assertTrue(initiative.pinned)
        self.assertEqual(initiative.parent, self.existing_pinned_initiative)

    @patch.object(ImportPipelineBCDataTask, "get_group_file_timestamp")
    def test_import_matching_by_initiative_custom_name(self, mock_get_group_file_timestamp):
        """Test imported initiative matches pinned and is marked as pinned."""
        mock_get_group_file_timestamp.return_value = timezone.now().timestamp()

        result = self.create_test_result(
            [
                SchemaInitiative(
                    initiative_name="Pinned Custom Name",
                    initiative_description="Test desc",
                    initiative_percentage=50,
                    epics=[
                        SchemaEpic(
                            epic_name="Epic 1",
                            epic_description="Epic desc",
                            epic_percentage=100,
                        )
                    ],
                )
            ]
        )

        task = ImportPipelineBCDataTask()
        task.import_results(self.organization, ContextualizationDayInterval.TWO_WEEKS, result)

        roadmap = Roadmap.latest_by_org(self.organization)
        initiative = Initiative.objects.get(name="Pinned Custom Name", roadmap=roadmap)
        InitiativeEpic.objects.get(name="Epic 1", initiative=initiative)
        self.assertTrue(initiative.pinned)
        self.assertEqual(initiative.parent, self.existing_pinned_initiative)

    @patch.object(ImportPipelineBCDataTask, "get_group_file_timestamp")
    def test_import_new_initiative_unpinned(self, mock_get_group_file_timestamp):
        """Test imported initiative without match is marked unpinned."""
        mock_get_group_file_timestamp.return_value = timezone.now().timestamp()

        result = self.create_test_result(
            [
                SchemaInitiative(
                    initiative_name="Brand New Initiative",
                    initiative_description="Test desc new",
                    initiative_percentage=30,
                    epics=[],
                )
            ]
        )

        task = ImportPipelineBCDataTask()
        task.import_results(self.organization, ContextualizationDayInterval.TWO_WEEKS, result)

        initiative = Initiative.objects.get(name="Brand New Initiative")
        self.assertFalse(initiative.pinned)
        self.assertIsNone(initiative.custom_name)

    @patch.object(ImportPipelineBCDataTask, "get_group_file_timestamp")
    def test_import_mixed_initiatives(self, mock_get_group_file_timestamp):
        """Test multiple initiatives, both matching and new."""
        mock_get_group_file_timestamp.return_value = timezone.now().timestamp()

        result = self.create_test_result(
            [
                SchemaInitiative(
                    initiative_name="Existing Initiative",
                    initiative_description="Existing desc",
                    initiative_percentage=70,
                    epics=[],
                ),
                SchemaInitiative(
                    initiative_name="Another Initiative",
                    initiative_description="Another desc",
                    initiative_percentage=40,
                    epics=[],
                ),
            ]
        )

        task = ImportPipelineBCDataTask()
        task.import_results(self.organization, ContextualizationDayInterval.TWO_WEEKS, result)

        roadmap = Roadmap.latest_by_org(self.organization)
        matched_initiative = Initiative.objects.get(name="Existing Initiative", roadmap=roadmap)
        skipped_initiative = Initiative.objects.get(name="Another Initiative")

        self.assertTrue(matched_initiative.pinned)
        self.assertEqual(matched_initiative.parent, self.existing_pinned_initiative)

        self.assertFalse(skipped_initiative.pinned)
        self.assertIsNone(skipped_initiative.custom_name)

    @patch.object(ImportPipelineBCDataTask, "get_group_file_timestamp")
    def test_import_matching_pinned_epic(self, mock_get_group_file_timestamp):
        """Test imported epic matches pinned epic in same initiative and is marked pinned."""
        # Add pinned epic under the pinned initiative
        existing_epic = InitiativeEpic.objects.create(
            name="Epic 1",
            custom_name="Pinned Epic Custom",
            pinned=True,
            initiative=self.existing_pinned_initiative,
        )

        mock_get_group_file_timestamp.return_value = timezone.now().timestamp()

        result = self.create_test_result(
            [
                SchemaInitiative(
                    initiative_name="Existing Initiative",
                    initiative_description="Test desc",
                    initiative_percentage=50,
                    epics=[
                        SchemaEpic(
                            epic_name="Pinned Epic Custom",
                            epic_description="Epic desc",
                            epic_percentage=100,
                        )
                    ],
                )
            ]
        )

        task = ImportPipelineBCDataTask()
        task.import_results(self.organization, ContextualizationDayInterval.TWO_WEEKS, result)

        roadmap = Roadmap.latest_by_org(self.organization)
        initiative = Initiative.objects.get(name="Existing Initiative", roadmap=roadmap)
        epic = InitiativeEpic.objects.get(name="Pinned Epic Custom", initiative=initiative)

        self.assertTrue(epic.pinned)
        self.assertEqual(epic.parent, existing_epic)

    @patch.object(ImportPipelineBCDataTask, "get_group_file_timestamp")
    def test_epic_not_matched_across_wrong_initiatives(self, mock_get_group_file_timestamp):
        """Test that epics are not matched if names overlap across unrelated initiatives."""
        # Another initiative with same epic name
        Initiative.objects.create(
            name="Unrelated Initiative",
            pinned=True,
            roadmap=self.existing_pinned_initiative.roadmap,
        )
        InitiativeEpic.objects.create(
            name="Epic 1",
            pinned=True,
            initiative=Initiative.objects.get(name="Unrelated Initiative"),
        )

        mock_get_group_file_timestamp.return_value = timezone.now().timestamp()

        result = self.create_test_result(
            [
                SchemaInitiative(
                    initiative_name="Existing Initiative",
                    initiative_description="Test desc",
                    initiative_percentage=50,
                    epics=[
                        SchemaEpic(
                            epic_name="Pinned Epic Custom",
                            epic_description="Epic desc",
                            epic_percentage=100,
                        )
                    ],
                )
            ]
        )

        task = ImportPipelineBCDataTask()
        task.import_results(self.organization, ContextualizationDayInterval.TWO_WEEKS, result)

        roadmap = Roadmap.latest_by_org(self.organization)
        initiative = Initiative.objects.get(name="Existing Initiative", roadmap=roadmap)
        epic = InitiativeEpic.objects.get(name="Pinned Epic Custom", initiative=initiative)

        self.assertTrue(epic.pinned)
        self.assertEqual(epic.parent, self.existing_pinned_epic_with_custom_name)

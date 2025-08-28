from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from compass.contextualization.models import (
    AnomalyInsightMessage,
    AnomalyInsights,
    Initiative,
    InitiativeEpic,
    QualitySummary,
    QualitySummaryByCategory,
    QualitySummaryByStage,
    QualitySummarySampleTicket,
    ReconcilableInitiative,
    Roadmap,
    TicketCompleteness,
)
from mvp.models import JiraProject, Organization


class DeleteOrganizationDataCommandTest(TestCase):
    """Test case for the `delete_organization_data` command.

    This test class is designed to verify the functioning of the command responsible for deleting
    organization-related data. The tests ensure that both hard and soft deletions are performed
    appropriately across multiple models associated with the organization. It creates the required
    data fixtures for testing and includes test methods to validate the data deletion logic.
    """

    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Organization",
            marked_for_deletion=True,
        )
        self.jira_project = JiraProject.objects.create(
            organization=self.organization,
            key="TEST",
            name="Test Project",
        )
        self.roadmap = Roadmap.objects.create(
            organization=self.organization,
            start_date="2024-01-01",
            end_date="2024-12-31",
            day_interval=14,
        )
        self.initiative = Initiative.objects.create(
            roadmap=self.roadmap,
            name="Test Initiative",
            percentage=50.00,
        )
        self.initiative_epic = InitiativeEpic.objects.create(
            initiative=self.initiative,
            name="Test Epic",
            percentage=25.0,
        )
        self.reconcilable_initiative = ReconcilableInitiative.objects.create(
            roadmap=self.roadmap,
            name="Test Reconcilable Initiative",
        )
        self.ticket_completeness = TicketCompleteness.objects.create(
            project=self.jira_project,
            ticket_id="TEST-123",
            name="Test Ticket",
            completeness_score=85,
            raw_completeness_score_evaluation="Good",
            completeness_score_explanation="Well structured ticket",
            llm_category="Story",
            stage="Done",
        )
        self.anomaly_insights = AnomalyInsights.objects.create(
            project=self.jira_project,
            anomaly_id="ANOM-001",
            anomaly_type="jira",
            title="Test Anomaly",
            insight="Test insight",
            evidence="Test evidence",
            significance_score=8,
            confidence_level="high",
            category="quality_impact",
        )
        self.anomaly_insight_message = AnomalyInsightMessage.objects.create(
            anomaly_insight=self.anomaly_insights,
            audience="developers",
            message_for_audience="Test message",
        )
        self.quality_summary = QualitySummary.objects.create(
            organization=self.organization,
            average_score=7.5,
            overview="Test overview",
        )
        self.quality_summary.projects.add(self.jira_project)
        self.quality_summary_by_stage = QualitySummaryByStage.objects.create(
            quality_summary=self.quality_summary,
            stage="Done",
            ticket_count=10,
            average_count=8.5,
            quality_category="Mature",
        )
        self.quality_summary_by_category = QualitySummaryByCategory.objects.create(
            quality_summary=self.quality_summary,
            category="Story",
            ticket_count=5,
            average_count=7.0,
            quality_category="Emerging",
        )
        self.quality_summary_sample_ticket = QualitySummarySampleTicket.objects.create(
            quality_summary=self.quality_summary,
            rank="top_3",
            issue_key="TEST-456",
            jira_completeness_score=90,
            stage_category="Done",
            llm_category="Story",
            quality_category="Advanced",
            explanation_jira_completeness_score="Excellent ticket quality",
        )

    @patch("mvp.management.commands.delete_organization_data.Command.delete_path")
    def test_hard_delete_all_contextualization_soft_delete_models(self, mock_delete_path):
        call_command("delete_organization_data", "--no-input", "--delete-organization")
        with self.subTest("should hard delete all related contextualization models"):
            self.assertFalse(Roadmap.global_objects.filter(organization=self.organization).exists())
            self.assertFalse(Initiative.global_objects.filter(roadmap__organization=self.organization).exists())
            self.assertFalse(
                InitiativeEpic.global_objects.filter(initiative__roadmap__organization=self.organization).exists()
            )
            self.assertFalse(
                ReconcilableInitiative.global_objects.filter(roadmap__organization=self.organization).exists()
            )
            self.assertFalse(TicketCompleteness.global_objects.filter(project__organization=self.organization).exists())
            self.assertFalse(AnomalyInsights.global_objects.filter(project__organization=self.organization).exists())
            self.assertFalse(
                AnomalyInsightMessage.global_objects.filter(
                    anomaly_insight__project__organization=self.organization
                ).exists()
            )
            self.assertFalse(QualitySummary.global_objects.filter(organization=self.organization).exists())
            self.assertFalse(
                QualitySummaryByStage.global_objects.filter(quality_summary__organization=self.organization).exists()
            )
            self.assertFalse(
                QualitySummaryByCategory.global_objects.filter(quality_summary__organization=self.organization).exists()
            )
            self.assertFalse(
                QualitySummarySampleTicket.global_objects.filter(
                    quality_summary__organization=self.organization
                ).exists()
            )

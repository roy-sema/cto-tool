import logging
from collections import defaultdict

from django.utils import timezone

from compass.contextualization.models import JiraProject, TicketCompleteness
from contextualization.pipelines.pipeline_D_jira_score_completeness.jira_completeness_score import (
    TickectCompletenessScoreResult,
)
from mvp.models import Organization

logger = logging.getLogger(__name__)


class ImportTicketCompletenessTask:
    def import_results(
        self,
        organization: Organization,
        ticket_completeness_scores: list[TickectCompletenessScoreResult],
    ):
        tickets_per_project = defaultdict(list)
        for ticket_completeness_score in ticket_completeness_scores:
            tickets_per_project[ticket_completeness_score.project_name].append(ticket_completeness_score)

        for project_name, tickets in tickets_per_project.items():
            try:
                project = JiraProject.objects.get(organization=organization, key=project_name)
            except JiraProject.DoesNotExist:
                logger.exception(
                    f"Project not found for organization",
                    extra={"organization": organization, "project_name": project_name},
                )
                continue

            for ticket in tickets:
                TicketCompleteness.objects.update_or_create(
                    ticket_id=ticket.issue_key,
                    project=project,
                    date=timezone.now().date(),
                    defaults={
                        "name": ticket.summary,
                        "description": ticket.description,
                        "assignee": ticket.assignee,
                        "stage": ticket.stage_category,
                        "reporter": None,
                        "priority": ticket.priority,
                        "completeness_score": ticket.jira_completeness_score,
                        "raw_completeness_score_evaluation": ticket.evaluation_jira_completeness_score,
                        "completeness_score_explanation": ticket.explanation_jira_completeness_score,
                        "llm_category": ticket.llm_category,
                        "quality_category": ticket.quality_category,
                    },
                )

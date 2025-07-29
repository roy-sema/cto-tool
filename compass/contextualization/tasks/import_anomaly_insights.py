import logging
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from compass.contextualization.models import AnomalyInsights, JiraProject
from contextualization.pipelines.anomaly_driven_insights.main import (
    GitCombinedInsights,
)
from contextualization.pipelines.jira_anomaly_driven_insights.jira_anomaly_insights import (
    JiraCombinedInsights,
)
from mvp.models import JiraProject, Organization, Repository


class ImportGitAnomalyInsightsTask:
    def import_results(self, organization: Organization, anomaly_insights: GitCombinedInsights):
        insights_per_repo = defaultdict(list)
        for insight in anomaly_insights.anomaly_insights + anomaly_insights.risk_insights:
            insights_per_repo[insight.repo].append(insight)

        # naive implementation to avoid data duplication if we re-run the pipeline
        # need to think how to correlate existing insights with new ones
        last_anomaly_insight = (
            AnomalyInsights.objects.filter(
                anomaly_type="git",
                repository__organization=organization,
            )
            .order_by("-created_at")
            .first()
        )
        if last_anomaly_insight and last_anomaly_insight.created_at.date() == timezone.now().date():
            logging.info(f"Skipping import of git anomaly insights for {organization} because it already exists")
            return

        anomaly_id = int(last_anomaly_insight.anomaly_id.split("-")[-1]) + 1 if last_anomaly_insight else 1

        with transaction.atomic():
            for repo_name, insights in insights_per_repo.items():
                try:
                    repo = Repository.objects.get(organization=organization, id=Repository.decode_id(repo_name))
                except Repository.DoesNotExist:
                    logging.exception(f"Repository {repo_name} not found for organization {organization}")
                    continue

                for insight in insights:
                    anomaly_insights = [
                        AnomalyInsights(
                            anomaly_id=f"AI-GIT-{anomaly_id}",
                            anomaly_type="git",
                            title=insight.title,
                            repository=repo,
                            insight=insight.insight,
                            evidence=insight.evidence,
                            significance_score=insight.significance_score,
                            confidence_level=insight.confidence_level,
                            category=insight.category,
                            source_commits=insight.sources,
                        )
                    ]
                    AnomalyInsights.objects.bulk_create(anomaly_insights)
                    anomaly_id += 1


class ImportJiraAnomalyInsightsTask:
    def import_results(self, organization: Organization, anomaly_insights: JiraCombinedInsights):
        insights_per_project = defaultdict(list)
        for insight in anomaly_insights.anomaly_insights + anomaly_insights.risk_insights:
            insights_per_project[insight.project].append(insight)

        last_anomaly_insight = (
            AnomalyInsights.objects.filter(
                anomaly_type="jira",
                project__organization=organization,
            )
            .order_by("-created_at")
            .first()
        )
        if last_anomaly_insight and last_anomaly_insight.created_at.date() == timezone.now().date():
            logging.info(f"Skipping import of jira anomaly insights for {organization} because it already exists")
            return

        anomaly_id = int(last_anomaly_insight.anomaly_id.split("-")[-1]) + 1 if last_anomaly_insight else 1

        with transaction.atomic():
            for project_name, insights in insights_per_project.items():
                try:
                    project = JiraProject.objects.get(organization=organization, key=project_name)
                except JiraProject.DoesNotExist:
                    logging.exception(f"Project {project_name} not found for organization {organization}")
                    continue

                for insight in insights:
                    anomaly_insights = [
                        AnomalyInsights(
                            anomaly_id=f"AI-JIRA-{anomaly_id}",
                            anomaly_type="jira",
                            project=project,
                            title=insight.title,
                            insight=insight.insight,
                            evidence=insight.evidence,
                            significance_score=insight.significance_score,
                            confidence_level=insight.confidence_level,
                            category=insight.category,
                            ticket_categories=insight.ticket_categories,
                            source_tickets=insight.source,
                        )
                    ]
                    AnomalyInsights.objects.bulk_create(anomaly_insights)
                    anomaly_id += 1

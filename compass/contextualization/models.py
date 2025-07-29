import datetime
from typing import TypedDict

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django_cte import CTE, with_cte
from multiselectfield import MultiSelectField

from contextualization.models.anomaly_insights import ConfidenceLevel, InsightCategory
from mvp.mixins import DecodePublicIdMixin
from mvp.models import (
    CustomUser,
    JiraProject,
    Organization,
    Repository,
    RepositoryGroup,
    TimestampedModel,
)
from mvp.services import ContextualizationDayInterval


class DayIntervalChoices(models.IntegerChoices):
    ONE_DAY = 1, "One day"
    ONE_WEEK = 7, "One week"
    TWO_WEEKS = 14, "Two weeks"


class SignificanceLevelChoices(models.IntegerChoices):
    TEN = 10, "10"
    NINE = 9, "9"
    EIGHT = 8, "8"
    SEVEN = 7, "7"


class TicketCategoryChoices(models.TextChoices):
    BUG = "Bug", "Bug"
    STORY = "Story", "Story"
    INCIDENT = "Incident", "Incident"
    REQUEST = "Request", "Request"
    MANUAL_TESTING = "Manual Testing", "Manual Testing"
    AUTOMATED_TESTING = "Automated Testing", "Automated Testing"
    OTHER = "Other", "Other"


class QualityCategoryChoices(models.TextChoices):
    INITIAL = "Initial", "Initial"
    EMERGING = "Emerging", "Emerging"
    MATURE = "Mature", "Mature"
    ADVANCED = "Advanced", "Advanced"
    UNCATEGORIZED = "Uncategorized", "Uncategorized"


class AnomalyTypeChoices(models.TextChoices):
    GIT = "git", "Git"
    JIRA = "jira", "Jira"


class ConfidenceLevelChoices(models.TextChoices):
    HIGH = ConfidenceLevel.HIGH.value, "High"
    MEDIUM = ConfidenceLevel.MEDIUM.value, "Medium"
    LOW = ConfidenceLevel.LOW.value, "Low"


class InsightCategoryChoices(models.TextChoices):
    TIMELINE_IMPACT = InsightCategory.TIMELINE_IMPACT.value, "Timeline Impact"
    QUALITY_IMPACT = InsightCategory.QUALITY_IMPACT.value, "Quality Impact"
    SCOPE_IMPACT = InsightCategory.SCOPE_IMPACT.value, "Scope Impact"
    RESOURCE_IMPACT = InsightCategory.RESOURCE_IMPACT.value, "Resource Impact"
    TECHNICAL_IMPACT = InsightCategory.TECHNICAL_IMPACT.value, "Technical Impact"
    FEATURE_ADDITION = InsightCategory.FEATURE_ADDITION.value, "Feature Addition"
    FEATURE_ENHANCEMENT = InsightCategory.FEATURE_ENHANCEMENT.value, "Feature Enhancement"
    OTHER = InsightCategory.OTHER.value, "Other"


class Roadmap(TimestampedModel):
    """Importing from git_data_summary_git_data_initiatives_combined.json"""

    summary = models.TextField(null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    day_interval = models.IntegerField(choices=DayIntervalChoices.choices)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="roadmaps")
    repository_group = models.ForeignKey(
        RepositoryGroup,
        on_delete=models.CASCADE,
        related_name="roadmaps",
        null=True,
        blank=True,
    )

    raw_roadmap = models.JSONField(null=True)
    raw_roadmap_reconciliation = models.JSONField(null=True)

    def __str__(self):
        return f"Roadmap [{self.organization.name}] | {self.id}"

    @classmethod
    def latest_by_org(
        cls,
        org: Organization,
        interval: ContextualizationDayInterval = ContextualizationDayInterval.TWO_WEEKS.value,
        repository_group_public_id: str | None = None,
    ):
        roadmap = cls.objects.filter(organization=org, day_interval=interval)
        if repository_group_public_id:
            repository_group_id = DecodePublicIdMixin().decode_id(repository_group_public_id)
            roadmap = roadmap.filter(repository_group_id=repository_group_id)

        return roadmap.order_by("-created_at").first()

    @classmethod
    def get_initiatives_data(cls, organization: Organization) -> dict:
        repository_groups = RepositoryGroup.objects.filter(organization=organization).all()
        latest_updated_at = 0
        initiatives_count = 0
        for repository_group in repository_groups:
            latest_roadmap = cls.latest_by_org(
                organization,
                repository_group_public_id=repository_group.public_id(),
            )
            if not latest_roadmap:
                continue

            latest_updated_at = max(latest_updated_at, latest_roadmap.updated_at.timestamp())
            initiatives_count += latest_roadmap.initiatives.count()

        initiatives = {
            "updated_at": latest_updated_at,
            "count": initiatives_count,
        }
        return initiatives


class Initiative(TimestampedModel):
    """Importing from git_data_summary_git_data_initiatives_combined.json"""

    name = models.CharField(max_length=255)
    justification = models.TextField(null=True)
    percentage = models.DecimalField(null=True, decimal_places=2, max_digits=5)
    percentage_tickets_done = models.DecimalField(decimal_places=2, default=0, max_digits=5)
    tickets_done = models.IntegerField(default=0)
    tickets_total = models.IntegerField(default=0)
    start_date = models.CharField(max_length=255, null=True)
    estimated_end_date = models.CharField(max_length=255, null=True)
    delivery_estimate = models.JSONField(null=True)

    pinned = models.BooleanField(default=False)
    custom_name = models.CharField(max_length=255, null=True, blank=True)
    disabled = models.BooleanField(default=False)

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    roadmap = models.ForeignKey(Roadmap, on_delete=models.CASCADE, related_name="initiatives")

    def __str__(self):
        return self.name


class InitiativeEpic(TimestampedModel):
    """Importing from git_data_summary_git_data_initiatives_combined.json"""

    name = models.CharField(max_length=255)
    description = models.TextField(null=True)
    percentage = models.FloatField(default=0)
    pinned = models.BooleanField(default=False)
    custom_name = models.CharField(max_length=255, null=True, blank=True)
    disabled = models.BooleanField(default=False)
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="epics")

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    def __str__(self):
        return self.name


class ReconcilableInitiative(TimestampedModel):
    """Importing from _git_data_summary_reconciliation_insights.json"""

    name = models.CharField(max_length=255)
    initiative_type = models.CharField(max_length=255, null=True)
    git_activity = models.TextField(null=True)
    jira_activity = models.TextField(null=True)
    roadmap = models.ForeignKey(Roadmap, on_delete=models.CASCADE, related_name="reconcilable_initiatives")

    def __str__(self):
        return self.name


class DailyMessage(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    date = models.DateField()
    raw_json = models.JSONField()

    class Meta:
        unique_together = ["organization", "date"]

    def __str__(self):
        return str(self.date)


class MessageFilterData(TypedDict):
    significance_levels: list[str]
    repository_groups: list[str]
    ticket_categories: list[str]


class MessageFilter(TimestampedModel):
    """used to store user filters for the daily/weekly messages"""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    day_interval = models.IntegerField(choices=DayIntervalChoices.choices)
    significance_levels = MultiSelectField(
        choices=SignificanceLevelChoices.choices,
        default=list,
        blank=True,
    )
    repository_groups = models.ManyToManyField(RepositoryGroup, blank=True)
    ticket_categories = MultiSelectField(
        choices=TicketCategoryChoices.choices,
        default=list,
        blank=True,
    )

    class Meta:
        unique_together = ("organization", "user", "day_interval")

    def __str__(self):
        return f"{self.organization.name} | {self.user.email} | {self.day_interval}"


class TicketCompleteness(TimestampedModel):
    # data taken from ticket management system (jira/github/etc)
    ticket_id = models.CharField(max_length=255)
    project = models.ForeignKey(JiraProject, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(null=True)

    assignee = models.TextField(null=True)
    reporter = models.TextField(null=True)
    priority = models.TextField(null=True)

    # generated by the pipeline
    completeness_score = models.IntegerField()
    raw_completeness_score_evaluation = models.TextField()
    completeness_score_explanation = models.TextField()
    llm_category = models.TextField(choices=TicketCategoryChoices.choices)
    stage = models.TextField()
    quality_category = models.TextField(choices=QualityCategoryChoices.choices, null=True)

    # Date field for unique constraint (one entry per day per project)
    date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ["ticket_id", "project", "date"]

    @classmethod
    def latest_ticket_data(cls, organization, at_date: datetime.date | None = None):
        # Select the latest ticket data for each ticket_id and project
        # This queryset is useful for most of the views, besides of the specific ticket time series
        qs = cls.objects.filter(project__organization=organization)
        if at_date:
            qs = qs.filter(date__lte=at_date)

        cte = CTE(qs.order_by("ticket_id", "project", "-date", "-id").distinct("ticket_id", "project"))
        return with_cte(cte, select=cte)


class AnomalyInsights(TimestampedModel):
    anomaly_id = models.TextField()
    anomaly_type = models.CharField(max_length=10, choices=AnomalyTypeChoices.choices)
    title = models.TextField()
    insight = models.TextField()
    evidence = models.TextField()
    significance_score = models.IntegerField()
    project = models.ForeignKey(JiraProject, on_delete=models.CASCADE, null=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, null=True)
    confidence_level = models.CharField(max_length=10, choices=ConfidenceLevelChoices.choices)
    category = models.CharField(max_length=50, choices=InsightCategoryChoices.choices)
    ticket_categories = ArrayField(
        models.CharField(max_length=255, choices=TicketCategoryChoices.choices), blank=True, default=list
    )
    source_tickets = ArrayField(models.CharField(max_length=255), blank=True, default=list)
    source_commits = ArrayField(models.CharField(max_length=255), blank=True, default=list)

    class Meta:
        unique_together = [
            "anomaly_id",
            "project",
        ]

from django.db import models

from mvp.models import TimestampedModel


class ChatHistoryStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETE = "complete", "Complete"
    ERROR = "error", "Error"


class ChatHistory(TimestampedModel):
    organization = models.ForeignKey(
        "mvp.Organization",
        on_delete=models.CASCADE,
    )
    created_by = models.ForeignKey(
        "mvp.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    prompt = models.TextField(blank=True, null=True)
    result = models.JSONField(default=None, blank=True, null=True)
    rollback_chat = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Used to rollback changes",
    )
    status = models.CharField(
        max_length=100,
        choices=ChatHistoryStatusChoices.choices,
        default=ChatHistoryStatusChoices.PENDING,
    )
    is_rollback = models.BooleanField(default=False)
    is_reset = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.prompt or f'ChatHistory ({self.id})'}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_active=True),
                name="unique_active_chat_history_per_organization",
            )
        ]
        verbose_name_plural = "chat histories"

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from mvp.mixins import PublicIdMixin
from mvp.models import CustomUser, TimestampedModel


class OverwriteStorage(FileSystemStorage):
    """
    Overwriting default behaviour otherwise it creates new files if the path is the same.
    TODO: if the file is unchanged and uploaded, then do nothing
    TODO: this should only affect files sent to the feedback endpoint
    """

    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            os.remove(name)
        return name


class GenAIFeedbackStatus(models.TextChoices):
    # TODO: unify with mvp models
    PURE = "pure", "Pure"
    BLENDED = "blended", "Blended"
    HUMAN = "human", "Human"


class GenAIFeedback(TimestampedModel, PublicIdMixin):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code_line_start = models.PositiveIntegerField()
    code_line_end = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=GenAIFeedbackStatus.choices)
    vote = models.IntegerField(default=0)
    comment = models.TextField(default="", blank=True)
    content_hash = models.CharField(max_length=255, default=None, blank=True, null=True)
    file_path = models.CharField(max_length=255)

    def get_filename_path(self, filename):
        base, ext = os.path.splitext(self.file_path)
        relative_file_path = f"{self.user.public_id()}/{base}_{self.content_hash}{ext}"
        return f"{settings.GENAI_FEEDBACK_DIRECTORY}/{relative_file_path}"

    file = models.FileField(upload_to=get_filename_path, storage=OverwriteStorage(), max_length=255)

    def get_comment_truncated(self):
        return self.comment if len(self.comment) < 50 else f"{self.comment[:50]}..."

    class Meta:
        verbose_name = "GenAI Feedback"
        verbose_name_plural = "GenAI Feedbacks"
        ordering = ["-created_at"]

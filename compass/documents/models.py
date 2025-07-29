from django.db import models

from cto_tool.storages import get_s3_storage
from mvp.mixins import PublicIdMixin
from mvp.models import TimestampedModel


def document_upload_to(instance, filename):
    # Using public_id of org to create path as org name isn't unique
    return f"compass/{instance.organization.public_id()}/{filename}"


class Document(PublicIdMixin, TimestampedModel):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey("mvp.Organization", on_delete=models.CASCADE)
    file = models.FileField(upload_to=document_upload_to, storage=get_s3_storage)
    uploaded_by = models.ForeignKey(
        "mvp.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name

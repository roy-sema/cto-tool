import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


def get_s3_storage():
    """
    Returns the appropriate storage backend dynamically based on the environment.
    """
    if settings.DEBUG and not settings.AWS_S3_FORCE_UPLOAD_TO_BUCKET:
        # Local storage for development
        return FileSystemStorage(
            location=os.path.join(settings.BASE_DIR, "media"),
        )
    else:
        # S3 storage for production
        return S3Boto3Storage(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            custom_domain=settings.AWS_S3_CUSTOM_DOMAIN,
        )

from pathlib import Path

import posthog
from azure.devops._file_cache import OPTIONS_CACHE, RESOURCE_CACHE
from django.apps import AppConfig
from django.conf import settings
from sentry_sdk.integrations.logging import ignore_logger

from contextualization.sentry_utils import init_sentry

BASE_DIR = Path(__file__).resolve().parent.parent


# disable caching for Azure DevOps SDK
# https://github.com/microsoft/azure-devops-python-api/issues/388
def no_op():
    pass


OPTIONS_CACHE.load = no_op
OPTIONS_CACHE.save = no_op
OPTIONS_CACHE.clear = no_op
RESOURCE_CACHE.load = no_op
RESOURCE_CACHE.save = no_op
RESOURCE_CACHE.clear = no_op


def sort_countries(country):
    if country == "united states":
        return 0
    if country == "canada":
        return 1
    return ord(country[0])


def sort_keys(obj):
    if isinstance(obj, dict):
        return {k: sort_keys(obj[k]) for k in sorted(obj, key=sort_countries)}
    if isinstance(obj, list):
        return [sort_keys(item) for item in obj]
    return obj


class MvpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mvp"

    def ready(self):
        import mvp.signals  # noqa: F401 # a ruff rule that would remove the unused import

        self.init_posthog()
        self.init_sentry()

    def init_posthog(self):
        if not settings.POSTHOG_PROJECT_API_KEY or settings.TESTING:
            posthog.disabled = True

            # leaving those empty raises an error, even with disabled flag
            posthog.project_api_key = "fake"
            posthog.host = "fake"

        else:
            posthog.project_api_key = settings.POSTHOG_PROJECT_API_KEY
            posthog.host = settings.POSTHOG_INSTANCE_ADDRESS

    def init_sentry(self):
        if settings.SENTRY_DSN and not settings.TESTING:
            init_sentry(
                environment="development" if settings.DEBUG else "production",
                sentry_dsn=settings.SENTRY_DSN,
            )
            ignore_logger("django.security.DisallowedHost")

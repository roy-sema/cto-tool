import logging

from django.utils import timezone

from compass.contextualization.models import DailyMessage
from mvp.models import Organization
from mvp.services import ContextualizationDayInterval
from mvp.services.contextualization_message_service import (
    ContextualizationMessageService,
)

logger = logging.getLogger(__name__)


class ImportDailyMessageTask:
    def import_results(self, organization: Organization):
        data = ContextualizationMessageService.get_for_day_interval(organization, ContextualizationDayInterval.ONE_DAY)
        if not data.get("last_updated"):
            logger.warning(
                "Unable to create daily message for org as nothing was updated",
                extra={"organization": organization.name, "data": data},
            )
            return

        DailyMessage.objects.update_or_create(
            organization=organization,
            date=timezone.now().date(),
            defaults={"raw_json": data},
        )

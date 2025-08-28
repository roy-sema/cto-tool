from datetime import datetime

from django.utils import timezone

from mvp.models import Organization
from mvp.services import ContextualizationDayInterval, ContextualizationService


class RawContextualizationService:
    """Collect all the contextualization data for a given organization and day interval, returning it in a raw dictionary format."""

    DATE_FORMAT = "%Y-%m-%d"

    @classmethod
    def get_for_day_interval(
        cls,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
    ) -> dict:
        output_data = {
            filename: cls.get_output_data(filename, organization, day_interval, pipeline)
            for filename, pipeline in cls.get_output_filenames()
        }
        updated_at = max([output["updated_at"] for output in output_data.values() if output["updated_at"] is not None])

        return {
            "organization": organization.name,
            "updated_at": updated_at,
            **output_data,
        }

    @staticmethod
    def get_output_filenames():
        return [
            (filename, pipeline)
            for pipeline, files in ContextualizationService.PIPELINE_TO_COPY_FILES_MAP.items()
            for filename in files.values()
        ]

    @classmethod
    def get_output_data(
        cls,
        filename: str,
        organization: Organization,
        day_interval: ContextualizationDayInterval,
        pipeline: str,
    ):
        data, updated_at = ContextualizationService.load_output_data(
            organization,
            filename,
            day_interval=day_interval,
        )
        parsed_updated_at = (
            datetime.fromtimestamp(updated_at, tz=timezone.utc).strftime(cls.DATE_FORMAT) if updated_at else None
        )
        return {
            "data": data,
            "date": parsed_updated_at,
            "updated_at": updated_at,
            "source_pipeline": pipeline,
        }

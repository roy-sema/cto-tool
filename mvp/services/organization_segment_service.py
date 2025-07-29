from datetime import datetime

from django.core.cache import cache
from django.db.models import Prefetch

from compass.integrations.integrations import CodacyIntegration
from mvp.models import (
    DataProviderConnection,
    DataProviderProject,
    DataProviderRecord,
    SegmentChoices,
)


class OrganizationSegmentService:
    CACHE_KEY_TEMPLATE = "{name}_{organization_id}"
    CACHE_TIMEOUT = 86400  # 1 day

    SEGMENT_DESCRIPTION = {
        SegmentChoices.ENTERPRISE_LEVEL: "At least 5 years old and 250-999 all-time developers.",
        SegmentChoices.GIANTS: "At least 5 years old and at least 1000 all-time developers.",
        SegmentChoices.GROWTH: "2-5 years old and 10-100 all time developers.",
        SegmentChoices.MATURE: "At least 10 years old and 25-100 all-time developers, or at least 5 years old and 100-250 all-time developers.",
        SegmentChoices.MID_SIZED: "2-5 years old and more than 100 developers, or 5-10 years old and 25-100 all-time developers.",
        SegmentChoices.SMALL_ESTABLISHED: "At least 5 years old and fewer than 25 all-time developers.",
        SegmentChoices.YOUNG_BIG_CODEBASE: "Less than 2 years old and fewer than 25 all-time developers and more than 500K lines of code, or 2-5 years old and more than 1M lines of code.",
        SegmentChoices.YOUNG_SMALL_CODEBASE: "Less than 2 years old and less than 500K lines of code, or 2-5 years old and fewer than 10 all-time developers and less than 1M lines of code.",
    }

    @property
    def segment_conditions(self):
        return [
            (
                lambda developers, lines, years: years >= 5 and developers >= 1000,
                SegmentChoices.GIANTS,
            ),
            (
                lambda developers, lines, years: years >= 5 and developers >= 250,
                SegmentChoices.ENTERPRISE_LEVEL,
            ),
            (
                lambda developers, lines, years: (years >= 2 and years < 5 and developers >= 100)
                or (years >= 5 and years < 10 and developers >= 25 and developers < 100),
                SegmentChoices.MID_SIZED,
            ),
            (
                lambda developers, lines, years: years >= 5 and developers < 25,
                SegmentChoices.SMALL_ESTABLISHED,
            ),
            (
                lambda developers, lines, years: (years >= 10 and developers >= 25 and developers < 100)
                or (years >= 5 and developers >= 100 and developers < 250),
                SegmentChoices.MATURE,
            ),
            (
                lambda developers, lines, years: (years < 2 and developers < 25 and lines < 500000)
                or (years < 2 and developers >= 25 and lines < 500000)
                or (years >= 2 and years < 5 and developers < 10 and lines < 1000000),
                SegmentChoices.YOUNG_SMALL_CODEBASE,
            ),
            (
                lambda developers, lines, years: (years < 2 and developers < 25 and lines >= 500000)
                or (years < 2 and developers >= 25 and lines >= 500000)
                or (years >= 2 and years < 5 and developers < 10 and lines >= 1000000),
                SegmentChoices.YOUNG_BIG_CODEBASE,
            ),
            (
                lambda developers, lines, years: years >= 2 and years < 5 and developers >= 10 and developers < 100,
                SegmentChoices.GROWTH,
            ),
        ]

    def __init__(self, organization):
        self.organization = organization
        self.cached_attributes = {}

    def num_developers(self):
        return self.organization.num_developers

    def num_developers_all_time(self):
        return self.organization.all_time_developers

    def num_lines(self):
        num = self.organization.num_code_lines
        if num is not None:
            return num

        if self.is_codacy_connected():
            return self.get_codacy_num_lines()

        return 0

    def num_years(self):
        return (
            datetime.utcnow().date().year - self.organization.first_commit_date.year
            if self.organization.first_commit_date
            else 0
        )

    def segment(self):
        num_developers = self.num_developers()
        num_lines = self.num_lines()
        num_years = self.num_years()

        for condition, segment in self.segment_conditions:
            if condition(num_developers, num_lines, num_years):
                return segment

        raise ValueError(
            f"Segment doesn't match any condition for developers: {num_developers}, lines: {num_lines},years: {num_years}."
        )

    def segment_description(self):
        return self.SEGMENT_DESCRIPTION[self.segment()]

    def is_codacy_connected(self):
        return self.get_or_set_cached_attribute("codacy_connected", self._is_codacy_connected)

    def _is_codacy_connected(self):
        try:
            connection = DataProviderConnection.objects.get(
                organization=self.organization, provider=CodacyIntegration().provider
            )
            return connection.is_connected
        except DataProviderConnection.DoesNotExist:
            return False

    def get_codacy_num_lines(self):
        return self.get_or_set_cached_attribute("codacy_num_lines", self._get_codacy_num_lines)

    def _get_codacy_num_lines(self):
        try:
            latest_record_prefetch = Prefetch(
                "dataproviderrecord_set",
                queryset=DataProviderRecord.objects.filter(field__name=CodacyIntegration.FIELD_NUM_LINES).order_by(
                    "-date_time"
                ),
                to_attr="latest_record",
            )

            projects = DataProviderProject.objects.filter(
                organization=self.organization, provider=CodacyIntegration().provider
            ).prefetch_related(latest_record_prefetch)

            num_lines = 0
            has_records = False
            for project in projects:
                if not project.latest_record:
                    continue

                record = project.latest_record[0]
                num_lines += record.value
                has_records = True

            return num_lines if has_records else None
        except DataProviderProject.DoesNotExist:
            return None

    def get_cache_key(self, name, organization_id):
        return self.CACHE_KEY_TEMPLATE.format(name=name, organization_id=organization_id)

    def get_or_set_cached_attribute(self, name, default):
        if name not in self.cached_attributes:
            self.cached_attributes[name] = cache.get_or_set(
                self.get_cache_key(name, self.organization.id),
                default,
                self.CACHE_TIMEOUT,
            )

        return self.cached_attributes[name]

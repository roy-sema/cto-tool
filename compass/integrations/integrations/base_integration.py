from abc import ABC, abstractmethod
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from mvp.models import (
    DataProvider,
    DataProviderConnection,
    DataProviderField,
    DataProviderMember,
    DataProviderMemberProjectRecord,
    DataProviderProject,
    DataProviderRecord,
)
from mvp.utils import get_since_until_last_record_months


class ProviderSingleton:
    _instance = None
    _providers = None

    def __new__(cls):
        # because database changes in tests, this breaks, so bypass it
        if cls._instance is None or settings.TESTING:
            cls._instance = super(ProviderSingleton, cls).__new__(cls)
            cls._providers = {provider.name: provider for provider in DataProvider.objects.all()}
        return cls._instance

    def get_provider(self, name):
        return self._providers.get(name)

    def add_provider(self, provider):
        self._providers[provider.name] = provider


class BaseIntegration(ABC):
    NUM_MONTHS_FETCH_NEW_PROJECT = 1

    @property
    @abstractmethod
    def modules(self):
        # A list of mvp.models.ModuleChoices
        pass

    @abstractmethod
    def fetch_data(self, connection):
        pass

    @staticmethod
    @abstractmethod
    def is_connection_connected(connection: DataProviderConnection) -> bool:
        pass

    def __init__(self):
        self._provider = None

    @property
    def provider(self):
        if self._provider is None:
            self._provider = self.get_or_create_provider(self.get_provider_name(), self.modules)
        return self._provider

    def get_or_create_provider(self, provider_name, modules):
        provider_singleton = ProviderSingleton()
        provider = provider_singleton.get_provider(provider_name)
        if provider is None or provider.modules != modules:
            provider, created = DataProvider.objects.get_or_create(
                name=provider_name,
                defaults={"modules": modules},
            )
            if not created and provider.modules != modules:
                provider.modules = modules
                provider.save()

            provider_singleton.add_provider(provider)

        return provider

    def get_or_create_field(self, name):
        field, created = DataProviderField.objects.get_or_create(name=name, provider=self.provider)
        return field

    def get_or_update_project(self, organization, name, external_id, meta=None):
        project, created = DataProviderProject.objects.get_or_create(
            organization=organization,
            provider=self.provider,
            external_id=external_id,
            defaults={"name": name, "meta": meta},
        )
        if not created and project.name != name or project.meta != meta:
            project.name = name
            project.meta = meta
            project.save()
        return project

    def get_or_update_member(self, organization, name, external_id, meta=None):
        member, created = DataProviderMember.objects.get_or_create(
            organization=organization,
            provider=self.provider,
            external_id=external_id or slugify(name),
            defaults={"name": name, "meta": meta},
        )
        if not created and member.name != name or member.meta != meta:
            member.name = name
            member.meta = meta
            member.save()
        return member

    def get_since_until(self, project, fields=None, member=None, return_last_record=False):
        """
        From NUM_MONTHS_FETCH_NEW_PROJECT months ago (first day of monty) until today,
        or from the next day after the last record until today
        """
        fields = fields or []
        last_record = (
            self.get_project_last_record(project, fields)
            if not member
            else self.get_member_project_last_record(member, project, fields)
        )
        since, until = get_since_until_last_record_months(last_record, self.NUM_MONTHS_FETCH_NEW_PROJECT)
        return (since, until) if not return_last_record else (since, until, last_record)

    def get_project_last_record(self, project, fields=None):
        fields = fields or []
        try:
            qs = DataProviderRecord.objects.filter(project=project)
            if fields:
                qs = qs.filter(field__in=fields)

            return qs.latest("date_time")
        except DataProviderRecord.DoesNotExist:
            return None

    def get_member_project_last_record(self, member, project, fields=None):
        fields = fields or []
        try:
            qs = DataProviderMemberProjectRecord.objects.filter(member=member, project=project)
            if fields:
                qs = qs.filter(field__in=fields)

            return qs.latest("date_time")
        except DataProviderMemberProjectRecord.DoesNotExist:
            return None

    def update_last_fetched(self, connection):
        connection.last_fetched_at = timezone.make_aware(datetime.utcnow())
        connection.save()

    @classmethod
    def get_provider_name(cls):
        return cls.__name__.replace("Integration", "")

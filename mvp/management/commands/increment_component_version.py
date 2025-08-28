from django.core.management.base import BaseCommand, CommandError

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.models import AppComponentChoices, AppComponentVersion


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Adds a new record to the version log of the given component"

    def add_arguments(self, parser):
        parser.add_argument("component", type=str, help="One of AppComponentChoices")

    def handle(self, *args, **options):
        component_key = options["component"]

        try:
            component = getattr(AppComponentChoices, component_key)
        except AttributeError as exc:
            raise CommandError(f'Component "{component_key}" does not exist. Check casing and spelling.') from exc

        version = self.increment_version(component)

        self.stdout.write(self.style.SUCCESS(f'Component "{component.label}" is now at version "{version}"'))

    def increment_version(self, component):
        version, created = AppComponentVersion.objects.get_or_create(component=component, defaults={"version": 1})
        if not created:
            version.version += 1
            version.save()

        return version.version

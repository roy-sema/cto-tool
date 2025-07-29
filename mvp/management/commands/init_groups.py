from django.core.management.base import BaseCommand

from mvp.mixins import InstrumentedCommandMixin, SingleInstanceCommandMixin
from mvp.tasks import InitGroupsTask


class Command(SingleInstanceCommandMixin, InstrumentedCommandMixin, BaseCommand):
    help = "Initialize user groups and permissions."

    def handle(self, *args, **kwargs):
        InitGroupsTask().run()

        self.stdout.write(self.style.SUCCESS("Groups and permissions initialized successfully!"))

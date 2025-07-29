import logging

from django.test import TestCase

from mvp.tasks import InitGroupsTask


class BaseViewTestCase(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        InitGroupsTask().run()
        logging.disable(logging.CRITICAL)

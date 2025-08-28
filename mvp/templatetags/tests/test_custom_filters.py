from django.test import TestCase

from mvp.templatetags.custom_filters import group_max


class TemplateFiltersTestCase(TestCase):
    def test_group_max(self, *args, **kwargs):
        with self.subTest("should return value list if length less than x"):
            result = group_max([1, 2, 3], 5)
            self.assertEqual(result, [[1, 2, 3]])
        with self.subTest("should return value chunked by x if length greater than x"):
            result = group_max([1, 2, 3, 4, 5, 6, 7], 5)
            self.assertEqual(
                result,
                [
                    [1, 2, 3, 4, 5],
                    [6, 7],
                ],
            )

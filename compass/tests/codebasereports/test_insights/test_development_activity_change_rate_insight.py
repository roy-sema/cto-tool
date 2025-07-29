import unittest

from compass.codebasereports.insights import DevelopmentActivityChangeRateInsight


class DevelopmentActivityChangeRateInsightTests(unittest.TestCase):
    def setUp(self):
        self.insight = DevelopmentActivityChangeRateInsight()

    def test_same_rate(self):
        self.assertEqual(self.insight.calculate_rate(10, 10), 0)
        self.assertEqual(self.insight.calculate_rate(0, 10), 0)
        self.assertEqual(self.insight.calculate_rate(10, 0), 0)
        self.assertEqual(self.insight.calculate_rate(0, 0), 0)

    def test_positive_rate(self):
        self.assertEqual(self.insight.calculate_rate(15, 10), 50)
        self.assertEqual(self.insight.calculate_rate(20, 10), 100)
        self.assertEqual(self.insight.calculate_rate(30, 10), 200)

    def test_negative_rate(self):
        self.assertEqual(self.insight.calculate_rate(10, 15), -50)
        self.assertEqual(self.insight.calculate_rate(10, 20), -100)
        self.assertEqual(self.insight.calculate_rate(10, 30), -200)

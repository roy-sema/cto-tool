from django.test import TestCase

from mvp.models import Organization, RepositoryGroup
from mvp.services.roi_service import ROIService


class ROIServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Org",
            avg_dev_annual_work_hours=1500,
            avg_developer_cost=100000,
            num_developers=5,
            tools_genai_monthly_cost=100,
        )

        self.group = RepositoryGroup.objects.create(
            name="Test Group 1",
            organization=self.organization,
            time_spent_coding_percentage=50,
            potential_productivity_improvement_percentage=20,
            max_genai_code_usage_percentage=40,
            num_developers=5,
        )

        self.group_no_roi = RepositoryGroup.objects.create(
            name="Test Group No ROI",
            organization=self.organization,
            time_spent_coding_percentage=0,
            potential_productivity_improvement_percentage=0,
            max_genai_code_usage_percentage=0,
            num_developers=0,
        )

    def test_get_potential_productivity_captured(self):
        result = ROIService.get_potential_productivity_captured(10, self.group)
        expected = 25  # (10 / 40) * 100
        self.assertEqual(result, expected)

    def test_get_potential_productivity_captured_no_roi(self):
        result = ROIService.get_potential_productivity_captured(10, self.group_no_roi)
        expected = 0
        self.assertEqual(result, expected)

    def test_get_productivity_achievement(self):
        result = ROIService.get_productivity_achievement(10, self.group)
        expected = 2.5
        self.assertEqual(result, expected)

    def test_has_total_impact(self):
        result = ROIService.has_total_impact(self.organization, self.group)
        self.assertTrue(result)

    def test_has_total_impact_no_roi(self):
        result = ROIService.has_total_impact(self.organization, self.group_no_roi)
        self.assertFalse(result)

    def test_get_hours_saved(self):
        result = ROIService.get_hours_saved(10, self.group, self.organization)
        expected = 187.5
        self.assertEqual(result, expected)

    def test_get_cost_saved(self):
        result = ROIService.get_cost_saved(10, self.group, self.organization)
        expected = 12500
        self.assertEqual(result, expected)

    def test_get_tools_cost_saved(self):
        result = ROIService.get_tools_cost_saved(self.group, self.organization)
        expected = 6000
        self.assertEqual(result, expected)

    def test_get_tools_cost_saved_percentage(self):
        result = ROIService.get_tools_cost_saved_percentage(10, self.group, self.organization)
        expected = 208.33333333333334
        self.assertAlmostEqual(result, expected, places=14)

    def test_get_tools_cost_saved_percentage_no_roi(self):
        result = ROIService.get_tools_cost_saved_percentage(10, self.group_no_roi, self.organization)
        self.assertIsNone(result)

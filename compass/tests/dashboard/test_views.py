from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from compass.dashboard.models import GitDiffContext
from compass.dashboard.views import DashboardView
from mvp.models import DataProvider, Organization, Repository
from mvp.services import ContextualizationService


class DashboardViewTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="TestOrg")
        self.provider = DataProvider.objects.create(
            name="GitHub",
        )
        self.repository = Repository.objects.create(
            organization=self.organization,
            provider=self.provider,
            owner="test-org",
            name="test-repo",
            external_id="1234",
        )

    def test_get_count_data_category_cleanup(self):
        categories = ["A", "B, C", "D - sth", "E - sth, else"]
        expected = ["A", "B", "C", "D", "E"]

        until = datetime.utcnow()
        since = until - timedelta(days=ContextualizationService.DEFAULT_DAY_INTERVAL.value - 1)

        GitDiffContext.objects.bulk_create(
            GitDiffContext(
                time=timezone.make_aware(since),
                repository=self.repository,
                sha=f"sha_{index}",
                file_path="test/file/path",
                git_diff_hash="1234",
                category=category,
            )
            for index, category in enumerate(categories)
        )

        result = DashboardView.get_count_data(self.organization, since, until)

        self.assertEqual(list(result[None].keys()), expected)

    def test_enhance_justification(self):
        repositories = [
            self.repository,
        ]
        justification_data = {
            "Refactor": {
                "justification": "Updated logic in test-repo and test-org/test-repo paths.",
                "examples": "See 'test', utils.py, directory/path, and helper_function.",
                "percentage": 50.0,
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, repositories)

        category = enhanced["Refactor"]

        self.assertEqual(
            category["justification"],
            "Updated logic in `test-repo` and `test-org/test-repo` paths.",
        )
        self.assertEqual(
            category["examples"],
            "See `test`, `utils.py`, `directory/path`, and `helper_function`.",
        )

        self.assertEqual(
            category["justification_text"],
            "Updated logic in test-repo and test-org/test-repo paths.",
        )
        self.assertEqual(
            category["examples_text"],
            "See 'test', utils.py, directory/path, and helper_function.",
        )

        self.assertEqual(enhanced["Refactor"]["percentage"], 50)

    def test_enhance_justification_without_repositories(self):
        justification_data = {
            "Refactor": {
                "justification": "test-repo",
                "examples": "test-org/test-repo",
                "percentage": 50.0,
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, [])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "test-repo")
        self.assertEqual(category["examples"], "`test-org/test-repo`")

        self.assertEqual(category["justification_text"], "test-repo")
        self.assertEqual(category["examples_text"], "test-org/test-repo")

        self.assertEqual(category["percentage"], 50)

    def test_enhance_justification_when_filename_ends_with_period(self):
        justification_data = {"Refactor": {"justification": "src/test_module.py."}}

        enhanced = DashboardView().enhance_justification(justification_data, [self.repository])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "`src/test_module.py`.")
        self.assertEqual(category["justification_text"], "src/test_module.py.")

        self.assertEqual(category["examples"], "")
        self.assertEqual(category["examples_text"], "")

        self.assertNotIn("percentage", category)

    def test_enhance_justification_when_text_enclosed_in_brackets(self):
        justification_data = {
            "Refactor": {
                "justification": "(src/test_module.py)",
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, [self.repository])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "(`src/test_module.py`)")
        self.assertEqual(category["justification_text"], "(src/test_module.py)")

        self.assertEqual(category["examples"], "")
        self.assertEqual(category["examples_text"], "")

        self.assertNotIn("percentage", category)

    def test_enhance_justification_when_text_has_comma(self):
        justification_data = {
            "Refactor": {
                "justification": "src/test_module.py,test-repo",
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, [self.repository])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "`src/test_module.py`,`test-repo`")
        self.assertEqual(category["justification_text"], "src/test_module.py,test-repo")

        self.assertEqual(category["examples"], "")
        self.assertEqual(category["examples_text"], "")

        self.assertNotIn("percentage", category)

    def test_enhance_justification_when_token_ends_with_comma(self):
        justification_data = {
            "Refactor": {
                "justification": "src/test_module.py,",
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, [self.repository])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "`src/test_module.py`,")
        self.assertEqual(category["justification_text"], "src/test_module.py,")

        self.assertEqual(category["examples"], "")
        self.assertEqual(category["examples_text"], "")

        self.assertNotIn("percentage", category)

    def test_enhance_justification_when_already_formatted(self):
        justification_data = {
            "Refactor": {
                "justification": "`src/test_module.py`",
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, [self.repository])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "`src/test_module.py`")
        self.assertEqual(category["justification_text"], "`src/test_module.py`")

        self.assertEqual(category["examples"], "")
        self.assertEqual(category["examples_text"], "")

        self.assertNotIn("percentage", category)

    def test_enhance_justification_when_multiple_dots(self):
        justification_data = {
            "Refactor": {
                "justification": "1.2.3",
            }
        }

        enhanced = DashboardView().enhance_justification(justification_data, [self.repository])

        category = enhanced["Refactor"]

        self.assertEqual(category["justification"], "`1.2.3`")
        self.assertEqual(category["justification_text"], "1.2.3")

        self.assertEqual(category["examples"], "")
        self.assertEqual(category["examples_text"], "")

        self.assertNotIn("percentage", category)

    def test_normalize_anomaly_insights(self):
        anomaly_insights = {
            "anomaly_insights": [
                {
                    "repo": self.repository.public_id(),
                    "insight": "Sudden spike in deletions",
                    "evidence": "50% increase in deletions on Apr 5",
                    "significance_score": 4,
                },
                {
                    "repo": self.repository.public_id(),
                    "insight": "Unusual commit pattern",
                    "evidence": "Commits clustered at 3am for 3 days",
                    "significance_score": 8,
                },
            ]
        }

        normalized = DashboardView.normalize_anomaly_insights(
            anomaly_insights, {self.repository.public_id(): self.repository}
        )

        self.assertIn(self.repository.public_id(), normalized.keys())

        insights = normalized[self.repository.public_id()]
        self.assertEqual(len(insights), 2)
        self.assertEqual(insights[0]["insight"], "Unusual commit pattern")
        self.assertEqual(insights[0]["evidence"], "Commits clustered at 3am for 3 days")
        self.assertEqual(insights[1]["insight"], "Sudden spike in deletions")
        self.assertEqual(insights[1]["evidence"], "50% increase in deletions on Apr 5")

    def test_normalize_anomaly_insights__none_in_score(self):
        anomaly_insights = {
            "anomaly_insights": [
                {
                    "repo": self.repository.public_id(),
                    "insight": "Sudden spike in deletions",
                    "evidence": "50% increase in deletions on Apr 5",
                    "significance_score": 1,
                },
                {
                    "repo": self.repository.public_id(),
                    "insight": "Unusual commit pattern",
                    "evidence": "Commits clustered at 3am for 3 days",
                    "significance_score": None,
                },
            ]
        }

        normalized = DashboardView.normalize_anomaly_insights(
            anomaly_insights, {self.repository.public_id(): self.repository}
        )

        self.assertIn(self.repository.public_id(), normalized.keys())

        insights = normalized[self.repository.public_id()]
        self.assertEqual(len(insights), 2)
        self.assertEqual(insights[0]["significance_score"], 1)
        self.assertEqual(insights[1]["significance_score"], None)

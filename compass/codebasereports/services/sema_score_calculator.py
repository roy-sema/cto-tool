import numpy as np
import pandas as pd

from mvp.models import MetricsChoices

from .sema_score_data_provider import SemaScoreDataProvider


class SemaScoreCalculator:
    QUARTILE_WEIGHT = {1: 1, 2: 0.67, 3: 0.33, 4: 0}

    MODULES = {
        "compliance": [
            {
                "name": "Code Security",
                "submodules": [
                    {
                        "name": "In-File Security",
                        "metric": MetricsChoices.HIGH_RISK_IN_FILE,
                        "weight": 10,
                    },
                    {
                        "name": "Third-Party Security",
                        "metric": MetricsChoices.HIGH_RISK_CVES,
                        "weight": 10,
                    },
                ],
            },
            {
                "name": "Open Source",
                "submodules": [
                    {
                        "name": "In-Reference Risk",
                        "metric": MetricsChoices.IN_REFERENCE_RISK_COUNT,
                        "weight": 10,
                    }
                ],
            },
            {
                "name": "Cyber Security",
                "submodules": [
                    {
                        "name": "Cyber Security Evaluation",
                        "metric": MetricsChoices.CYBER_SECURITY_EVALUATION,
                        "weight": 5,
                    },
                ],
            },
        ],
        "product": [
            {
                "name": "Code Quality",
                "submodules": [
                    {
                        "name": "Unit Testing Ratio",
                        "metric": MetricsChoices.IN_HOUSE_CURRENT_TEST_RATIO,
                        "weight": 10,
                    }
                ],
            },
            {
                "name": "Process",
                "submodules": [
                    {
                        "name": "Commit Analysis Evaluation",
                        "metric": MetricsChoices.COMMIT_ANALYSIS_EVALUATION,
                        "weight": 5,
                    },
                    {
                        "name": "Average Developer Activity Evaluation",
                        "metric": MetricsChoices.AVERAGE_DEVELOPER_ACTIVITY_EVALUATION,
                        "weight": 10,
                    },
                    {
                        "name": "Developers and Development Activity Evaluation",
                        "metric": MetricsChoices.DEVELOPERS_AND_DEVELOPMENT_ACTIVITY_EVALUATION,
                        "weight": 5,
                    },
                ],
            },
            {
                "name": "Team",
                "submodules": [
                    {
                        "name": "Developers Retention Ratio",
                        "metric": MetricsChoices.DEVELOPERS_RETENTION_RATIO,
                        "weight": 25,
                    },
                ],
            },
        ],
    }

    SCORE_SEMA = "sema"
    SCORE_COMPLIANCE = "compliance"
    SCORE_PRODUCT = "product"

    @property
    def modules_df(self):
        mapping = {
            "metric": [],
            "weight": [],
            "module_name": [],
            "module_type": [],
            "submodule_name": [],
        }

        for module_type, modules in self.MODULES.items():
            for module in modules:
                for submodule in module["submodules"]:
                    mapping["metric"].append(submodule["metric"])
                    mapping["weight"].append(submodule["weight"])
                    mapping["module_name"].append(module["name"])
                    mapping["module_type"].append(module_type)
                    mapping["submodule_name"].append(submodule["name"])

        return pd.DataFrame(mapping)

    @property
    def metrics(self):
        return self.modules_df["metric"].tolist()

    def __init__(self, organization):
        self.organization = organization
        self.provider = SemaScoreDataProvider(organization)

    def get_scores(self, date):
        self.init_scores(date)
        self.update_scores()

        return (
            self.get_score_value(self.SCORE_SEMA),
            self.get_score_value(self.SCORE_COMPLIANCE),
            self.get_score_value(self.SCORE_PRODUCT),
        )

    def init_scores(self, date):
        ref_metrics = pd.DataFrame.from_records(self.provider.get_reference_metrics())
        self.metric_values = self.get_metric_values(date, ref_metrics) if not ref_metrics.empty else None

        self._sema_score = [0, 0]  # numerator, denominator
        self._product_score = [0, 0]
        self._compliance_score = [0, 0]

    def update_scores(self):
        for metric in self.metrics:
            quartile = self.get_metric_quartile(metric)
            if not quartile:
                continue

            self._update_score(self.SCORE_SEMA, metric, quartile)

            module_type = self.get_modules_df_metric_value(metric, "module_type")
            self._update_score(module_type, metric, quartile)

    def _update_score(self, score_name, metric, quartile):
        score = self.get_score_by_name(score_name)
        metric_weight = self.get_modules_df_metric_value(metric, "weight")

        score[0] += metric_weight * self.QUARTILE_WEIGHT[quartile]
        score[1] += metric_weight

    def get_score_by_name(self, name):
        return getattr(self, f"_{name}_score")

    def get_score_value(self, score_name):
        numerator, denominator = self.get_score_by_name(score_name)
        return int(np.ceil(numerator * 100 / denominator)) if denominator else None

    def get_modules_df_metric_value(self, metric, column):
        return self.modules_df[self.modules_df["metric"] == metric][column].values[0]

    def get_metric_quartile(self, metric):
        return self.metric_values[metric] if self.metric_values is not None and metric in self.metric_values else 0

    def get_percentiles(self, ref_metrics, metric):
        result = ref_metrics[(ref_metrics["metric"] == metric)]
        if result.empty:
            raise ValueError(f"There are no records for metric '{metric}'")

        return {
            25: result[result["percentile"] == 25]["value"].values[0],
            50: result[result["percentile"] == 50]["value"].values[0],
            75: result[result["percentile"] == 75]["value"].values[0],
        }

    def get_quartile(self, value, percentiles):
        if value <= percentiles[25]:
            return 1

        if value <= percentiles[50]:
            return 2

        if value <= percentiles[75]:
            return 3

        return 4

    def get_metric_values(self, date, ref_metrics):
        """
        Returns the values for each metric on a given date
        """
        result = {}
        for metric in self.metrics:
            value = self.provider.get_metric_value(metric, date)
            if value is None:
                continue

            percentiles = self.get_percentiles(ref_metrics, metric)
            quartile = self.get_quartile(value, percentiles)
            result[metric.lower()] = [quartile]

        result_df = pd.DataFrame(result)
        return result_df.iloc[0] if not result_df.empty else None

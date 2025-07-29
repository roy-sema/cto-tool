from abc import ABC, abstractmethod

from compass.codebasereports.insights import BaseInsight


class WarningsBenchmarkInsight(BaseInsight, ABC):
    PHASE_INITIAL = {
        "phase": "Initial",
        "level": "red",
        "action": "Additional investment in security remediation should be a high priority.",
    }
    PHASE_EMERGING = {
        "phase": "Emerging",
        "level": "orange",
        "action": "Additional investment in security remediation is likely necessary.",
    }
    PHASE_MATURE = {
        "phase": "Mature",
        "level": "yellow",
        "action": "Additional investment in security remediation may not be necessary.",
    }
    PHASE_ADVANCED = {
        "phase": "Advanced",
        "level": "green",
        "action": "Additional investment in security remediation may not be necessary.",
    }

    HOURS_PER_ISSUE = 4
    SPRINT_WEEKS = 2
    WEEK_DEV_HOURS = 31.32
    YEAR_DEV_HOURS = 1568

    @property
    def phase_conditions(self):
        return [
            (lambda r: r <= 29, self.PHASE_ADVANCED),
            (lambda r: 30 <= r <= 69, self.PHASE_MATURE),
            (lambda r: 70 <= r <= 84, self.PHASE_EMERGING),
            (lambda r: r >= 85, self.PHASE_INITIAL),
        ]

    @abstractmethod
    def get_reference_records(self):
        pass

    def get_insight(self, num_issues, organization):
        percentile = self.find_percentile(num_issues, self.get_percentiles())
        is_bottom = percentile > 50
        position = "bottom" if is_bottom else "top"

        return {
            **self.get_value_description(percentile, self.phase_conditions),
            "percentile": 100 - percentile if is_bottom else percentile,
            "position": position,
            "remediation": self.get_remediation_costs(num_issues, organization),
        }

    def get_percentiles(self):
        records = self.get_reference_records()

        percentiles = []
        total_records = len(records)

        # calculate 1-100 percentiles
        for index, record in enumerate(records, start=1):
            percentile = ((index - 1) / (total_records - 1) * 99) + 1
            percentiles.append({"value": record["value"], "percentile": round(percentile)})

        return percentiles

    def find_percentile(self, value, percentiles):
        for percentile in percentiles:
            if value <= percentile["value"]:
                return percentile["percentile"]

        return 100

    def get_remediation_costs(self, num_issues, organization):
        if not num_issues:
            return None

        num_hours = num_issues * self.HOURS_PER_ISSUE

        sprint_capacity = organization.num_developers * self.WEEK_DEV_HOURS * self.SPRINT_WEEKS

        num_sprints = num_hours / sprint_capacity

        hourly_rate = organization.avg_developer_cost / self.YEAR_DEV_HOURS

        dollars = num_hours * hourly_rate

        return {
            "hours": round(num_hours),
            "dollars": round(dollars),
            "sprints": round(num_sprints, 1),
        }

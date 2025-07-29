from compass.codebasereports.insights import ChangeRateInsight
from compass.integrations.integrations import GitHubIntegration


class CommitChangeRateInsight(ChangeRateInsight):
    RATE_CONSISTENT = {
        "status": "consistent",
        "level": "green",
    }
    RATE_DECREASING = {
        "status": "decreasing",
        "level": "yellow",
        "description": "This could be due to having fewer developers, devs going on breaks, process changes, or working on fixes rather than new features.",
    }
    RATE_DECREASING_SIGNIFICANTLY = {
        "status": "significantly decreasing",
        "level": "yellow",
        "description": "This could be due to having fewer developers, devs going on breaks, process changes, or working on fixes rather than new features.",
    }
    RATE_INCREASING = {
        "status": "increasing",
        "level": "green",
        "description": "This could be due to adding more developers, devs returning from breaks, process changes, or working on new features rather than fixes.",
    }
    RATE_INCREASING_SIGNIFICANTLY = {
        "status": "significantly increasing",
        "level": "green",
        "description": "This could be due to adding more developers, devs returning from breaks, process changes, or working on new features rather than fixes.",
    }

    @property
    def field_name(self):
        return GitHubIntegration.FIELD_COMMIT_COUNT

    @property
    def rate_conditions(self):
        return [
            (lambda r: r >= 20, self.RATE_INCREASING_SIGNIFICANTLY),
            (lambda r: 10 <= r < 20, self.RATE_INCREASING),
            (lambda r: -10 <= r <= 10, self.RATE_CONSISTENT),
            (lambda r: -20 <= r < -10, self.RATE_DECREASING),
            (lambda r: r <= -20, self.RATE_DECREASING_SIGNIFICANTLY),
        ]

    def get_insight(self, records, since, until):
        return super().get_insight(records, since, until)

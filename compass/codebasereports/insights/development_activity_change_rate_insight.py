from compass.codebasereports.insights import ChangeRateInsight
from compass.integrations.integrations import GitHubIntegration


class DevelopmentActivityChangeRateInsight(ChangeRateInsight):
    RATE_CONSISTENT = {
        "status": "consistent",
        "level": "green",
    }
    RATE_DECREASING = {
        "status": "decreasing",
        "level": "yellow",
        "description": "Development activity is decreasing.",
    }
    RATE_DECREASING_SIGNIFICANTLY = {
        "status": "significantly decreasing",
        "level": "yellow",
        "description": "Development activity is significantly decreasing. Besides the factors that could cause a change to committing activity, this could be caused by the activity returning to normal after a bulk change to code.",
    }
    RATE_DECREASING_SPIKE = {
        "status": "shows an unusual spike",
        "level": "yellow",
        "description": "Development activity shows an unusual spike. Most likely there was a previous bulk change to the code and now development activity is back to normal.",
    }
    RATE_INCREASING = {
        "status": "increasing",
        "level": "green",
        "description": "Development activity is increasing. ",
    }
    RATE_INCREASING_SIGNIFICANTLY = {
        "status": "significantly increasing",
        "level": "green",
        "description": "Development activity is significantly increasing. Besides the factors that could cause a change to committing activity, this could be caused by a bulk change to code.",
    }
    RATE_INCREASING_SPIKE = {
        "status": "shows an unusual spike",
        "level": "yellow",
        "description": "Development activity shows an unusual spike. Most likely there was a bulk change to the code.",
    }

    @property
    def field_name(self):
        return GitHubIntegration.FIELD_FILE_CHANGE_COUNT

    @property
    def rate_conditions(self):
        return [
            (lambda r: r >= 100, self.RATE_INCREASING_SPIKE),
            (lambda r: 20 <= r < 100, self.RATE_INCREASING_SIGNIFICANTLY),
            (lambda r: 10 <= r < 20, self.RATE_INCREASING),
            (lambda r: -10 <= r <= 10, self.RATE_CONSISTENT),
            (lambda r: -20 <= r < -10, self.RATE_DECREASING),
            (lambda r: -100 <= r < -20, self.RATE_DECREASING_SIGNIFICANTLY),
            (lambda r: r <= -100, self.RATE_DECREASING_SPIKE),
        ]

    def get_insight(self, records, since, until):
        return super().get_insight(records, since, until)

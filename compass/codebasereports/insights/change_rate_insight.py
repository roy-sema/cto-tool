from abc import abstractmethod
from datetime import timedelta

from compass.codebasereports.insights import BaseInsight


class ChangeRateInsight(BaseInsight):
    @property
    @abstractmethod
    def field_name(self):
        pass

    @property
    @abstractmethod
    def rate_conditions(self):
        pass

    def get_insight(self, records, since, until):
        days = (until - since).days
        previous_since = since - timedelta(days=days)

        changes_current, changes_previous = self.aggregate_records_by_period(records, since, until, previous_since)

        rate = self.calculate_rate(changes_current, changes_previous)

        return {
            **self.get_value_description(rate, self.rate_conditions),
            "rate": rate,
        }

    def aggregate_records_by_period(self, records, current_since, current_until, previous_since):
        total_current = 0
        total_previous = 0
        for record in records:
            if record["field__name"] != self.field_name:
                continue

            if current_since <= record["date_time"] < current_until:
                total_current += record["value"]
            elif previous_since <= record["date_time"] < current_since:
                total_previous += record["value"]

        return (total_current, total_previous)

    def calculate_rate(self, value_current, value_previous):
        if not value_current or not value_previous or value_current == value_previous:
            return 0

        if value_current > value_previous:
            return ((value_current - value_previous) / value_previous) * 100

        return (value_previous - value_current) / value_current * -100

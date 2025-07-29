from abc import ABC, abstractmethod


class BaseInsight(ABC):
    @abstractmethod
    def get_insight(self):
        pass

    def get_value_description(self, value, conditions):
        for condition, description in conditions:
            if condition(value):
                return description

        raise ValueError(f"Value {value} doesn't match any condition.")

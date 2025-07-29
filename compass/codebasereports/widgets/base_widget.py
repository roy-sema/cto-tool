from abc import ABC, abstractmethod


class BaseWidget(ABC):
    @abstractmethod
    def get_widgets(self):
        pass

    def __init__(self, organization):
        self.organization = organization

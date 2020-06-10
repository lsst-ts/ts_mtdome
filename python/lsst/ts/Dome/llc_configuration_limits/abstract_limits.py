__all__ = ["AbstractLimits"]

from abc import ABC, abstractmethod


class AbstractLimits(ABC):
    """An abstract base class for holding the configuration limits for the lower level components.

    It holds common methods.
    """

    @abstractmethod
    def validate(self, configuration_parameters):
        pass

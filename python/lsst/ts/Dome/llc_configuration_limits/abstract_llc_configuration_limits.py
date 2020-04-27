from abc import ABC, abstractmethod


class AbstractLlcConfigurationLimits(ABC):
    """An abstract base class for holding the configuration limits for the lower level components. The
    class holds common methods and constant values.

    Note that SAL expresses angles in degrees while the lower level components express angles in radians.
    This class will convert any value expressed in degrees to radians.
    """

    @abstractmethod
    def validate(self, configuration_parameters):
        pass

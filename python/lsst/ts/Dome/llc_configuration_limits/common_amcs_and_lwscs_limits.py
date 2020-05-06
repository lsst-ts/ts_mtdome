from abc import abstractmethod
from .abstract_limits import AbstractLimits
import math

DEGREES_TO_RADIANS = math.pi / 180.0


class CommonAmcsAndLwscsLimits(AbstractLimits):
    @abstractmethod
    def validate(self, configuration_parameters):
        pass

    # noinspection PyMethodMayBeStatic
    def validate_common_parameters(self, configuration_parameters, common_limits):
        """Validate the data are against the configuration limits of the lower level component.

        If necessary it also converts the values expressed in deg/s^n to rad/s^n (with n = 1, 2 or 3).

        Parameters
        ----------
        configuration_parameters: `dict`
            The configuration parameters to validate and possibly convert.
        common_limits: `dict`
            The limits shared by AMCS and LWSCS. The names are the same but the values differ.

        Returns
        -------
        converted_configuration_parameters: `dict`
            The converted configuration parameters.
        """
        # This dict will hold the converted values which we will return at the end of thius function if all
        # validations are passed. If a configuration parameter
        converted_configuration_parameters = {}

        for key in common_limits.keys():
            # Validate the provided value  against the limit.
            if configuration_parameters[key] <= common_limits[key]:
                converted_configuration_parameters[key] = (
                    common_limits[key] * DEGREES_TO_RADIANS
                )
            else:
                # If the value is larger than the limit, raise a ValueError
                raise ValueError(
                    f"The value {configuration_parameters[key]} for {key} is larger than the "
                    f"limit {common_limits[key]}."
                )

        # Check if any unknown configuration parameters remain.
        extra_keys = set(configuration_parameters.keys()) - common_limits.keys()
        if extra_keys:
            # If yes then raise a ValueError.
            raise KeyError(
                f"Found these unknown configuration parameters: {configuration_parameters.keys()}."
            )

        # All configuration values fall within their limits and no unknown configuration parameters were
        # found so we can return the converted values.
        return converted_configuration_parameters

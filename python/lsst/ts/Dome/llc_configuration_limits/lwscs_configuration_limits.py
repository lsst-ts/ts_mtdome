from .abstract_llc_configuration_limits import AbstractLlcConfigurationLimits
import math

DEGREES_TO_RADIANS = math.pi / 180.0


class LwscsConfigurationLimits(AbstractLlcConfigurationLimits):
    """This class holds the limits of the configuration values for the LWSCS lower level component. It will
    validate any set of configuration parameters againt these limits. It will also convert any
    configuration parameter values expressed in deg/s^n to rad/s^n (with n = 1, 2 or 3).
    """

    def __init__(self):
        self.jmax = 3.0  # Maximum jerk in deg/s^3
        self.amax = 0.75  # Maximum acceleration in deg/s^2
        self.vmax = 1.5  # Maximum velocity in deg/s

    def validate_and_convert_from_degrees_to_radians(self, configuration_parameters):
        """Validates the data are against the configuration limits of the lower level component. If
        necessary it also converts the values expressed in deg/s^n to rad/s^n (with n = 1, 2 or 3).

        Parameters
        ----------
        configuration_parameters: `dict`
            The configuration parameters to validate and possibly convert.

        Returns
        -------
        converted_configuration_parameters: `dict`
            The converted configuration parameters.
        """
        # This dict will hold the converted values which we will return at the end of thius function if all
        # validations are passed.
        converted_configuration_parameters = {}

        # Validate the provided value for max jerk (in deg/s^3) against the limit (in deg/s^3).
        if configuration_parameters["jmax"] <= self.jmax:
            # If the value is smaller than or equal to the limit, convert to rad/s^3.
            converted_configuration_parameters["jmax"] = (
                configuration_parameters["jmax"] * DEGREES_TO_RADIANS
            )
            # Remove the key so we can check later if any unknown configuration parameters remain.
            del configuration_parameters["jmax"]
        else:
            # If the value is larger than the limit, raise a ValueError
            raise ValueError(
                f"The value {configuration_parameters['jmax']} for jmax is larger than the limit {self.jmax}."
            )

        # Validate the provided value for max acceleration (in deg/s^3) against the limit (in deg/s^3).
        if configuration_parameters["amax"] <= self.jmax:
            # If the value is smaller than or equal to the limit, convert to rad/s^2.
            converted_configuration_parameters["amax"] = (
                configuration_parameters["amax"] * DEGREES_TO_RADIANS
            )
            # Remove the key so we can check later if any unknown configuration parameters remain.
            del configuration_parameters["amax"]
        else:
            raise ValueError(
                f"The value {configuration_parameters['amax']} for amax is larger than the limit {self.amax}."
            )

        # Validate the provided value for max velocity (in deg/s^3) against the limit (in deg/s^3).
        if configuration_parameters["vmax"] <= self.vmax:
            # If the value is smaller than or equal to the limit, convert to rad/s.
            converted_configuration_parameters["vmax"] = (
                configuration_parameters["vmax"] * DEGREES_TO_RADIANS
            )
            # Remove the key so we can check later if any unknown configuration parameters remain.
            del configuration_parameters["vmax"]
        else:
            raise ValueError(
                f"The value {configuration_parameters['vmax']} for vmax is larger than the limit {self.vmax}."
            )

        # Check if any unknown configuration parameters remain.
        if configuration_parameters.keys():
            # If yes then raise a ValueError.
            raise ValueError(
                f"Found these unknown configuration parameters: {configuration_parameters.keys()}."
            )

        # All configuration values fall within their limits and no unknown configuration parameters were
        # found so we can return the converted values.
        return converted_configuration_parameters

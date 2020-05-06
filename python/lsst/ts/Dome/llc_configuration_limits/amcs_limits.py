from .common_amcs_and_lwscs_limits import CommonAmcsAndLwscsLimits


class AmcsLimits(CommonAmcsAndLwscsLimits):
    """This class holds the limits of the configuration values for the AMCS lower level component. It will
    validate any set of configuration parameters againt these limits. It will also convert any
    configuration parameter values expressed in deg/s^n to rad/s^n (with n = 1, 2 or 3).

    Hardcoded parameters:
    jmax : `float` (optional)
        Maximum jerk, in deg/s^3
    amax : `float` (optional)
        Maximum acceleration, in deg/s^2
    vmax : `float` (optional)
        Maximum velocity, in deg/s
    """

    def __init__(self):
        self.jmax = 3.0  # Maximum jerk in deg/s^3
        self.amax = 0.75  # Maximum acceleration in deg/s^2
        self.vmax = 1.5  # Maximum velocity in deg/s

    def validate(self, configuration_parameters):
        """Validate the data are against the configuration limits of the lower level component.

        If necessary it also converts the values expressed in deg/s^n to rad/s^n (with n = 1, 2 or 3).

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
        converted_configuration_parameters = self.validate_common_parameters(
            configuration_parameters,
            {"jmax": self.jmax, "amax": self.amax, "vmax": self.vmax},
        )

        # All configuration values fall within their limits and no unknown configuration parameters were
        # found so we can return the converted values.
        return converted_configuration_parameters

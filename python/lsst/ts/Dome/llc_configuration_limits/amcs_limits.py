# This file is part of ts_Dome.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["AmcsLimits"]

import math

from .common_amcs_and_lwscs_limits import CommonAmcsAndLwscsLimits


class AmcsLimits(CommonAmcsAndLwscsLimits):
    """This class holds the limits of the configuration values for the AMCS
    lower level component.

    Parameters
    ----------
    Hardcoded parameters:
    jmax : `float` (optional)
        Maximum jerk, in deg/s^3
    amax : `float` (optional)
        Maximum acceleration, in deg/s^2
    vmax : `float` (optional)
        Maximum velocity, in deg/s
    """

    def __init__(self):
        self.jmax = math.radians(3.0)  # Maximum jerk in rad/s^3
        self.amax = math.radians(0.75)  # Maximum acceleration in rad/s^2
        self.vmax = math.radians(1.5)  # Maximum velocity in rad/s

    def validate(self, configuration_parameters):
        """Validate the data are against the configuration limits of the lower
        level component.

        If necessary it also converts the values expressed in deg/s^n to
        rad/s^n (with n = 1, 2 or 3).

        Parameters
        ----------
        configuration_parameters: `dict`
            The configuration parameters to validate and possibly convert.

        Returns
        -------
        converted_configuration_parameters: `dict`
            The converted configuration parameters.
        """

        # This dict will hold the converted values which we will return at the
        # end of thius function if all validations are passed.
        converted_configuration_parameters = self.validate_common_parameters(
            configuration_parameters, {"jmax": self.jmax, "amax": self.amax, "vmax": self.vmax},
        )

        # All configuration values fall within their limits and no unknown
        # configuration parameters were found so we can return the converted
        # values.
        return converted_configuration_parameters

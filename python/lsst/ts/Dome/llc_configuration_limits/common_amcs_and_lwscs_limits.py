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

__all__ = ["CommonAmcsAndLwscsLimits"]

from abc import abstractmethod
from .abstract_limits import AbstractLimits
import math


class CommonAmcsAndLwscsLimits(AbstractLimits):
    """Helper class that handles parameter limits common between AMCS and
    LWSCS.
    """

    @abstractmethod
    def validate(self, configuration_parameters):
        pass

    # noinspection PyMethodMayBeStatic
    def extract_scalar_values_from_common_parameters(self, configuration_parameters):
        # DM-25758: All config values are passed on as arrays so in these cases
        # we need to extract the only value in the array.
        config_params_without_arrays = {}
        for field in configuration_parameters:
            if field in ("jmax", "amax", "vmax"):
                config_params_without_arrays[field] = configuration_parameters[field][0]
            else:
                config_params_without_arrays[field] = configuration_parameters[field]
        return config_params_without_arrays

    # noinspection PyMethodMayBeStatic
    def validate_common_parameters(self, configuration_parameters, common_limits):
        """Validate the data are against the configuration limits of the lower
        level component.

        If necessary it also converts the values expressed in deg/s^n to
        rad/s^n (with n = 1, 2 or 3).

        Parameters
        ----------
        configuration_parameters: `dict`
            The configuration parameters to validate and possibly convert.
        common_limits: `dict`
            The limits shared by AMCS and LWSCS. The names are the same but
            the values differ.

        Returns
        -------
        converted_configuration_parameters: `dict`
            The converted configuration parameters.
        """
        # This dict will hold the converted values which we will return at the
        # end of this function if all validations are passed.
        converted_configuration_parameters = {}

        for key in common_limits.keys():
            # Validate the provided value  against the limit.
            if math.radians(configuration_parameters[key]) <= common_limits[key]:
                converted_configuration_parameters[key] = math.radians(common_limits[key])
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

        # All configuration values fall within their limits and no unknown
        # configuration parameters were found so we can return the converted
        # values.
        return converted_configuration_parameters

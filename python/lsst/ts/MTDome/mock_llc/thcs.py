# This file is part of ts_MTDome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
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

__all__ = ["ThcsStatus", "NUM_THERMO_SENSORS"]

import logging
import numpy as np

from lsst.ts import salobj
from .base_mock_llc import BaseMockStatus
from ..enums import LlcMotionState

NUM_THERMO_SENSORS = 13


class ThcsStatus(BaseMockStatus):
    """Represents the status of the Thermal Control System in simulation
    mode.
    """

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("MockThcsStatus")
        self.status = LlcMotionState.CLOSED
        self.temperature = np.zeros(NUM_THERMO_SENSORS, dtype=float)

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        time_diff = current_tai - self.command_time_tai
        self.log.debug(
            f"current_tai = {current_tai}, self.command_time_tai = {self.command_time_tai}, "
            f"time_diff = {time_diff}"
        )
        self.llc_status = {
            "status": self.status.name,
            "temperature": self.temperature.tolist(),
            "timestampUTC": current_tai,
        }
        self.log.debug(f"thcs_state = {self.llc_status}")

    async def setTemperature(self, temperature: float) -> None:
        """Set the preferred temperature in the dome. It should mock cooling
        down or warming up but it doesn't.

        Parameters
        ----------
        temperature: `float`
            The preferred temperature (degrees Celsius). In reality this should
            be a realistic temperature in the range of about -30 C to +40 C but
            the provided temperature is not checked against this range.
        """
        self.command_time_tai = salobj.current_tai()
        self.status = LlcMotionState.OPEN
        self.temperature[:] = temperature

    async def exit_fault(self) -> None:
        """Clear the fault state."""
        self.status = LlcMotionState.STATIONARY

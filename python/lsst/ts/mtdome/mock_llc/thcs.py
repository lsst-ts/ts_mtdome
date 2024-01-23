# This file is part of ts_mtdome.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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
from lsst.ts.xml.enums.MTDome import MotionState

from ..enums import InternalMotionState
from .base_mock_llc import BaseMockStatus

NUM_THERMO_SENSORS = 13


class ThcsStatus(BaseMockStatus):
    """Represents the status of the Thermal Control System in simulation
    mode.
    """

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("MockThcsStatus")
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.temperature = np.zeros(NUM_THERMO_SENSORS, dtype=float)
        self.current_state = MotionState.DISABLED
        self.target_state = MotionState.DISABLED

    async def evaluate_state(self) -> None:
        """Evaluate the state and perform a state transition if necessary."""
        match self.target_state:
            case MotionState.ENABLED:
                if self.current_state == MotionState.DISABLED:
                    self.current_state = MotionState.ENABLING
                elif self.current_state == MotionState.ENABLING:
                    self.current_state = MotionState.ENABLED
            case MotionState.DISABLED:
                if self.current_state == MotionState.ENABLED:
                    self.current_state = MotionState.DISABLING
                elif self.current_state == MotionState.DISABLING:
                    self.current_state = MotionState.DISABLED
            case _:
                # Not a valid state, so empty.
                pass

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        await self.evaluate_state()
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": self.current_state.name,
                "operationalMode": self.operational_mode.name,
            },
            "temperature": self.temperature.tolist(),
            "timestampUTC": current_tai,
        }
        self.log.debug(f"thcs_state = {self.llc_status}")

    async def set_temperature(self, temperature: float, current_tai: float) -> None:
        """Set the preferred temperature in the dome.

        Parameters
        ----------
        temperature: `float`
            The preferred temperature (degrees Celsius). In reality this should
            be a realistic temperature in the range of about -30 C to +40 C but
            the provided temperature is not checked against this range.
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        self.temperature[:] = temperature

    async def start_cooling(self, current_tai: float) -> None:
        """Start cooling.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        self.target_state = MotionState.ENABLED

    async def stop_cooling(self, current_tai: float) -> None:
        """Stop cooling.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        self.target_state = MotionState.DISABLED

    async def exit_fault(self) -> None:
        """Clear the fault state."""
        self.current_state = InternalMotionState.STATIONARY

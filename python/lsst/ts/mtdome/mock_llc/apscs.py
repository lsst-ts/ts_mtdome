# This file is part of ts_mtdome.
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

__all__ = ["ApscsStatus", "NUM_SHUTTERS"]

import logging

import numpy as np
from lsst.ts import utils

from ..enums import LlcMotionState
from .base_mock_llc import BaseMockStatus

NUM_SHUTTERS = 2
_NUM_MOTORS = 4


class ApscsStatus(BaseMockStatus):
    """Represents the status of the Aperture Shutter Control System in
    simulation mode.
    """

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("MockApscsStatus")

        # Variables holding the status of the mock Aperture Shutter
        self.status = [LlcMotionState.CLOSED, LlcMotionState.CLOSED]
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.position_actual = np.zeros(NUM_SHUTTERS, dtype=float)
        self.position_commanded = 0.0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.resolver_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.power_draw = 0.0
        # Keep track of being in error state or not.
        self.motion_state_in_error = False
        # Keep track of which drives are in error state.
        self.drives_in_error_state = [False] * _NUM_MOTORS

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
            "status": {
                "messages": self.messages,
                "status": [s.name for s in self.status],
                "operationalMode": self.operational_mode.name,
            },
            "positionActual": self.position_actual.tolist(),
            "positionCommanded": self.position_commanded,
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTemperature": self.drive_temperature.tolist(),
            "resolverHeadRaw": self.resolver_head_raw.tolist(),
            "resolverHeadCalibrated": self.resolver_head_calibrated.tolist(),
            "powerDraw": self.power_draw,
            "timestampUTC": current_tai,
        }
        self.log.debug(f"apcs_state = {self.llc_status}")

    async def openShutter(self) -> None:
        """Open the shutter."""
        self.command_time_tai = utils.current_tai()
        self.status = [LlcMotionState.OPEN, LlcMotionState.OPEN]
        # Both positions are expressed in percentage.
        self.position_actual = np.full(NUM_SHUTTERS, 100.0, dtype=float)
        self.position_commanded = 100.0

    async def closeShutter(self) -> None:
        """Close the shutter."""
        self.command_time_tai = utils.current_tai()
        self.status = [LlcMotionState.CLOSED, LlcMotionState.CLOSED]
        # Both positions are expressed in percentage.
        self.position_actual = np.zeros(NUM_SHUTTERS, dtype=float)
        self.position_commanded = 0.0

    async def stopShutter(self) -> None:
        """Stop all motion of the shutter."""
        self.command_time_tai = utils.current_tai()
        self.status = [LlcMotionState.STOPPED, LlcMotionState.STOPPED]

    async def go_stationary(self) -> None:
        """Stop shutter motion and engage the brakes."""
        self.command_time_tai = utils.current_tai()
        self.status = [LlcMotionState.STATIONARY, LlcMotionState.STATIONARY]

    async def reset_drives_shutter(self, reset: list[int]) -> None:
        """Reset one or more Aperture Shutter drives.

        Parameters
        ----------
        reset: array of int
            Desired reset action to execute on each Aperture Shutter drive: 0
            means don't reset, 1 means reset.

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        for i, val in enumerate(reset):
            if val == 1:
                self.drives_in_error_state[i] = False

    async def search_zero_shutter(self) -> None:
        """Search the zero position of the Aperture Shutter, which is the
        closed position. This is necessary in case the ApSCS (Aperture Shutter
        Control system) was shutdown with the Aperture Shutter not fully open
        or fully closed. For now `closeShutter` simply is called but this may
        change.
        """
        await self.closeShutter()

    async def exit_fault(self) -> None:
        """Clear the fault state."""
        if True in self.drives_in_error_state:
            raise RuntimeError("Make sure to reset drives before exiting from fault.")

        self.status = [LlcMotionState.STATIONARY, LlcMotionState.STATIONARY]
        self.motion_state_in_error = False

    async def set_fault(self, drives_in_error: list[int]) -> None:
        """Set the LlcMotionState of ApSCS to fault and set the drives in
        drives_in_error to error.

        Parameters
        ----------
        drives_in_error : array of int
            Desired error action to execute on each ApSCS drive: 0 means don't
            set to error, 1 means set to error.

        Notes
        -----
        This function is not mapped to a command that MockMTDomeController can
        receive. It is intended to be set by unit test cases.
        """
        self.motion_state_in_error = True
        self.status = [LlcMotionState.ERROR, LlcMotionState.ERROR]
        for i, val in enumerate(drives_in_error):
            if val == 1:
                self.drives_in_error_state[i] = True

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

__all__ = ["ApscsStatus"]

import logging
import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from ..llc_status import LlcStatus

_NUM_MOTORS = 4


class ApscsStatus(BaseMockStatus):
    """Represents the status of the Aperture Shutter Control System in
    simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockApscsStatus")
        # variables holding the status of the mock Aperture Shutter
        self.status = LlcStatus.CLOSED
        self.position_actual = 0.0
        self.position_commanded = 0.0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.resolver_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.power_draw = 0.0

    async def determine_status(self, current_tai):
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        time_diff = current_tai - self.command_time_tai
        self.log.debug(
            f"current_tai = {current_tai}, self.command_time_tai = {self.command_time_tai}, "
            f"time_diff = {time_diff}"
        )
        self.llc_status = {
            "status": self.status.value,
            "positionActual": self.position_actual,
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

    async def openShutter(self):
        """Open the shutter."""
        self.log.debug("Received command 'openShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.OPEN
        # Both positions are expressed in percentage.
        self.position_actual = 100.0
        self.position_commanded = 100.0

    async def closeShutter(self):
        """Close the shutter."""
        self.log.debug("Received command 'closeShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.CLOSED
        # Both positions are expressed in percentage.
        self.position_actual = 0.0
        self.position_commanded = 0.0

    async def stopShutter(self):
        """Stop all motion of the shutter."""
        self.log.debug("Received command 'stopShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.STOPPED

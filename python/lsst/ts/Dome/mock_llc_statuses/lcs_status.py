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

__all__ = ["MotionState"]

import logging
import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from lsst.ts.idl.enums.Dome import MotionState

_NUM_LOUVERS = 34
_NUM_MOTORS = 68


class LcsStatus(BaseMockStatus):
    """Represents the status of the Louvers Control System in simulation mode.

    If the position of a louver is non-zero, it is considered OPEN even if it
    only is 1% open. If the position of a louver is zero, it is considered
    closed.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockLcsStatus")
        # variables holding the status of the mock Louvres
        self.status = np.full(_NUM_LOUVERS, MotionState.CLOSED.value, dtype=object)
        self.position_actual = np.zeros(_NUM_LOUVERS, dtype=float)
        self.position_commanded = np.zeros(_NUM_LOUVERS, dtype=float)
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
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
            "status": self.status.tolist(),
            "positionActual": self.position_actual.tolist(),
            "positionCommanded": self.position_commanded.tolist(),
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTemperature": self.drive_temperature.tolist(),
            "encoderHeadRaw": self.encoder_head_raw.tolist(),
            "encoderHeadCalibrated": self.encoder_head_calibrated.tolist(),
            "powerDraw": self.power_draw,
            "timestampUTC": current_tai,
        }
        self.log.debug(f"lcs_state = {self.llc_status}")

    async def setLouvers(self, position):
        """Set the position of the louver with the given louver_id.

        Parameters
        ----------
        position: array of float
            An array with the positions (percentage) to set the louvers to. 0
            means closed, 180 means wide open, -1 means do not move. These
            limits are not checked.
        """
        self.command_time_tai = salobj.current_tai()
        for louver_id, pos in enumerate(position):
            if pos >= 0:
                if pos > 0:
                    self.status[louver_id] = MotionState.OPEN.value
                else:
                    self.status[louver_id] = MotionState.CLOSED.value
                self.position_actual[louver_id] = pos
                self.position_commanded[louver_id] = pos

    async def closeLouvers(self):
        """Close all louvers."""
        self.command_time_tai = salobj.current_tai()
        self.status[:] = MotionState.CLOSED.value
        self.position_actual[:] = 0.0
        self.position_commanded[:] = 0.0

    async def stopLouvers(self):
        """Stop all motion of all louvers."""
        self.command_time_tai = salobj.current_tai()
        self.status[:] = MotionState.STOPPED.value

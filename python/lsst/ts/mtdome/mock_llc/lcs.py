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

__all__ = ["LcsStatus", "CURRENT_PER_MOTOR", "NUM_LOUVERS", "NUM_MOTORS_PER_LOUVER"]

import logging

import numpy as np
from lsst.ts import utils
from lsst.ts.idl.enums.MTDome import MotionState

from ..enums import InternalMotionState
from ..power_draw_constants import LOUVERS_POWER_DRAW
from .base_mock_llc import DOME_VOLTAGE, BaseMockStatus

NUM_LOUVERS = 34
NUM_MOTORS_PER_LOUVER = 2

# Current drawn per louver [A].
_CURRENT_PER_LOUVER = LOUVERS_POWER_DRAW / NUM_LOUVERS / DOME_VOLTAGE
# Current drawn per motor by the louvers [A].
CURRENT_PER_MOTOR = _CURRENT_PER_LOUVER / NUM_MOTORS_PER_LOUVER


class LcsStatus(BaseMockStatus):
    """Represents the status of the Louvers Control System in simulation mode.

    If the position of a louver is non-zero, it is considered OPEN even if it
    only is 1% open. If the position of a louver is zero, it is considered
    closed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("MockLcsStatus")

        # Variables holding the status of the mock Louvres
        self.status = np.full(NUM_LOUVERS, MotionState.CLOSED.name, dtype=object)
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.position_actual = np.zeros(NUM_LOUVERS, dtype=float)
        self.position_commanded = np.zeros(NUM_LOUVERS, dtype=float)
        self.drive_torque_actual = np.zeros(
            NUM_LOUVERS * NUM_MOTORS_PER_LOUVER, dtype=float
        )
        self.drive_torque_commanded = np.zeros(
            NUM_LOUVERS * NUM_MOTORS_PER_LOUVER, dtype=float
        )
        self.drive_current_actual = np.zeros(
            NUM_LOUVERS * NUM_MOTORS_PER_LOUVER, dtype=float
        )
        self.drive_temperature = np.full(
            NUM_LOUVERS * NUM_MOTORS_PER_LOUVER, 20.0, dtype=float
        )
        self.encoder_head_raw = np.zeros(
            NUM_LOUVERS * NUM_MOTORS_PER_LOUVER, dtype=float
        )
        self.encoder_head_calibrated = np.zeros(
            NUM_LOUVERS * NUM_MOTORS_PER_LOUVER, dtype=float
        )
        self.power_draw = 0.0

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        # Determine the current drawn by the louvers.
        for index, motion_state in enumerate(self.status):
            # Louver motors come in pairs of two.
            if motion_state == MotionState.MOVING:
                self.drive_current_actual[
                    index * NUM_MOTORS_PER_LOUVER : (index + 1) * NUM_MOTORS_PER_LOUVER
                ] = CURRENT_PER_MOTOR
                self.power_draw = LOUVERS_POWER_DRAW
            else:
                self.drive_current_actual[
                    index * NUM_MOTORS_PER_LOUVER : (index + 1) * NUM_MOTORS_PER_LOUVER
                ] = 0.0
                self.power_draw = 0.0
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": self.status.tolist(),
                "operationalMode": self.operational_mode.name,
            },
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

    async def setLouvers(self, position: list[float]) -> None:
        """Set the position of the louver with the given louver_id.

        Parameters
        ----------
        position: array of float
            An array with the positions (percentage) to set the louvers to. 0
            means closed, 180 means wide open, -1 means do not move. These
            limits are not checked.
        """
        self.command_time_tai = utils.current_tai()
        pos: float = 0
        for louver_id, pos in enumerate(position):
            if pos >= 0:
                if pos > 0:
                    self.status[louver_id] = MotionState.OPEN.name
                else:
                    self.status[louver_id] = MotionState.CLOSED.name
                self.position_actual[louver_id] = pos
                self.position_commanded[louver_id] = pos

    async def closeLouvers(self) -> None:
        """Close all louvers."""
        self.command_time_tai = utils.current_tai()
        self.status[:] = MotionState.CLOSED.name
        self.position_actual[:] = 0.0
        self.position_commanded[:] = 0.0

    async def stopLouvers(self) -> None:
        """Stop all motion of all louvers."""
        self.command_time_tai = utils.current_tai()
        self.status[:] = MotionState.STOPPED.name

    async def go_stationary(self) -> None:
        """Stop louvers motion and engage the brakes."""
        self.command_time_tai = utils.current_tai()
        self.status[:] = InternalMotionState.STATIONARY.name

    async def exit_fault(self) -> None:
        """Clear the fault state."""
        self.status[:] = InternalMotionState.STATIONARY.name

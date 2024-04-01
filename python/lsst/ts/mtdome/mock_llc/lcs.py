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
from lsst.ts.xml.enums.MTDome import MotionState

from ..enums import InternalMotionState
from ..power_management.power_draw_constants import LOUVERS_POWER_DRAW
from .base_mock_llc import DOME_VOLTAGE, BaseMockStatus

NUM_LOUVERS = 34
NUM_MOTORS_PER_LOUVER = 2

# Current drawn per louver [A].
_CURRENT_PER_LOUVER = LOUVERS_POWER_DRAW / NUM_LOUVERS / DOME_VOLTAGE
# Current drawn per motor by the louvers [A].
CURRENT_PER_MOTOR = _CURRENT_PER_LOUVER / NUM_MOTORS_PER_LOUVER

# Motion velocity of the louvers, equalling 100 % / 30 s
MOTION_VELOCITY = 100 / 30


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
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.start_position = np.zeros(NUM_LOUVERS, dtype=float)
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

        # State machine related attributes.
        self.current_state = np.full(
            NUM_LOUVERS, InternalMotionState.STATIONARY.name, dtype=object
        )
        self.start_state = np.full(
            NUM_LOUVERS, InternalMotionState.STATIONARY.name, dtype=object
        )
        self.target_state = np.full(
            NUM_LOUVERS, InternalMotionState.STATIONARY.name, dtype=object
        )

    async def evaluate_state(self, current_tai: float, louver_id: int) -> None:
        """Evaluate the state and perform a state transition if necessary.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        louver_id : `int`
            The louver id.
        """
        match self.target_state[louver_id]:
            case MotionState.STOPPED.name:
                await self._handle_stopped(louver_id)
            case InternalMotionState.STATIONARY.name:
                await self._handle_stationary(current_tai, louver_id)
            case _:
                # Not a valid state, so empty.
                self.log.warning(
                    f"Not handling invalid target state {self.target_state[louver_id]}"
                )

    async def _handle_stopped(self, louver_id: int) -> None:
        # STATIONARY is the final state for the setLouvers, closeLouveres and
        # stopLovers (with brakes engaged) commands.
        if self.target_state[louver_id] == InternalMotionState.STATIONARY.name:
            self.current_state[louver_id] = MotionState.ENGAGING_BRAKES.name

    async def _handle_stationary(self, current_tai: float, louver_id: int) -> None:
        match self.current_state[louver_id]:
            case InternalMotionState.STATIONARY.name:
                if self.start_state[louver_id] in [
                    MotionState.OPENING.name,
                    MotionState.CLOSING.name,
                ]:
                    self.current_state[louver_id] = (
                        MotionState.ENABLING_MOTOR_POWER.name
                    )
            case MotionState.ENABLING_MOTOR_POWER.name:
                self.current_state[louver_id] = MotionState.MOTOR_POWER_ON.name
            case MotionState.MOTOR_POWER_ON.name:
                self.current_state[louver_id] = MotionState.GO_NORMAL.name
            case MotionState.GO_NORMAL.name:
                self.current_state[louver_id] = MotionState.DISENGAGING_BRAKES.name
            case MotionState.DISENGAGING_BRAKES.name:
                self.current_state[louver_id] = MotionState.BRAKES_DISENGAGED.name
            case MotionState.BRAKES_DISENGAGED.name:
                self.current_state[louver_id] = MotionState.MOVING.name
            case MotionState.MOVING.name:
                await self._handle_moving(current_tai, louver_id)
            case MotionState.STOPPING.name:
                self.current_state[louver_id] = MotionState.STOPPED.name
            case MotionState.STOPPED.name:
                await self._handle_stopped(louver_id)
            case MotionState.ENGAGING_BRAKES.name:
                self.current_state[louver_id] = MotionState.BRAKES_ENGAGED.name
            case MotionState.BRAKES_ENGAGED.name:
                self.current_state[louver_id] = MotionState.GO_STATIONARY.name
            case MotionState.GO_STATIONARY.name:
                self.current_state[louver_id] = MotionState.DISABLING_MOTOR_POWER.name
            case MotionState.DISABLING_MOTOR_POWER.name:
                self.current_state[louver_id] = MotionState.MOTOR_POWER_OFF.name
            case MotionState.MOTOR_POWER_OFF.name:
                self.start_state[louver_id] = InternalMotionState.STATIONARY.name
                self.current_state[louver_id] = InternalMotionState.STATIONARY.name
                self.target_state[louver_id] = InternalMotionState.STATIONARY.name

    async def _handle_moving(self, current_tai: float, louver_id: int) -> None:
        time_needed = (
            abs(self.position_commanded[louver_id] - self.start_position[louver_id])
            / MOTION_VELOCITY
        )
        time_so_far = current_tai - self.command_time_tai
        time_frac = 1.0
        if not np.isclose(time_needed, 0.0):
            time_frac = time_so_far / time_needed
        if time_frac >= 1.0:
            self.position_actual[louver_id] = self.position_commanded[louver_id]
            self.current_state[louver_id] = MotionState.STOPPING.name
        else:
            distance = (
                self.position_commanded[louver_id] - self.start_position[louver_id]
            )
            self.position_actual[louver_id] = (
                self.start_position[louver_id] + distance * time_frac
            )

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        # Determine the current drawn by the louvers.
        for louver_id, motion_state in enumerate(self.current_state):
            await self.evaluate_state(current_tai, louver_id)
            # Louver motors come in pairs of two.
            if motion_state == MotionState.MOVING.name:
                self.drive_current_actual[
                    louver_id
                    * NUM_MOTORS_PER_LOUVER : (louver_id + 1)
                    * NUM_MOTORS_PER_LOUVER
                ] = CURRENT_PER_MOTOR
                self.power_draw = LOUVERS_POWER_DRAW
            else:
                self.drive_current_actual[
                    louver_id
                    * NUM_MOTORS_PER_LOUVER : (louver_id + 1)
                    * NUM_MOTORS_PER_LOUVER
                ] = 0.0
                self.power_draw = 0.0
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": self.current_state.tolist(),
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

    async def setLouvers(self, position: list[float], current_tai: float) -> None:
        """Set the position of the louver with the given louver_id.

        Parameters
        ----------
        position: array of float
            An array with the positions (percentage) to set the louvers to. 0
            means closed, 100 means wide open, -1 means do not move. These
            limits are not checked.
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        pos: float = 0
        for louver_id, pos in enumerate(position):
            if 0 <= pos <= 100 and not np.isclose(self.position_actual[louver_id], pos):
                if pos > 0:
                    self.start_state[louver_id] = MotionState.OPENING.name
                    self.target_state[louver_id] = InternalMotionState.STATIONARY.name
                else:
                    self.start_state[louver_id] = MotionState.CLOSING.name
                    self.target_state[louver_id] = InternalMotionState.STATIONARY.name
                self.start_position = np.copy(self.position_actual)
                self.position_commanded[louver_id] = pos

    async def closeLouvers(self, current_tai: float) -> None:
        """Close all louvers.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        for louver_id in range(NUM_LOUVERS):
            if not np.isclose(self.position_actual[louver_id], 0.0):
                self.start_state[louver_id] = MotionState.CLOSING.name
                self.target_state[louver_id] = InternalMotionState.STATIONARY.name
        self.position_commanded[:] = 0.0

    async def stopLouvers(self, current_tai: float) -> None:
        """Stop all motion of all louvers.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        self.start_state[:] = MotionState.STOPPING.name
        self.target_state[:] = MotionState.STOPPED.name

    async def go_stationary(self, current_tai: float) -> None:
        """Stop louvers motion and engage the brakes.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        self.target_state[:] = InternalMotionState.STATIONARY.name

    async def exit_fault(self, current_tai: float) -> None:
        """Clear the fault state.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        self.start_state[:] = MotionState.GO_STATIONARY.name
        self.target_state[:] = InternalMotionState.STATIONARY.name

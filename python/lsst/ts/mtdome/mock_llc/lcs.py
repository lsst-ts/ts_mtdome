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
        self.current_tai = 0.0
        self.current_state = np.full(
            NUM_LOUVERS, InternalMotionState.STATIONARY.name, dtype=object
        )
        self.start_state = np.full(
            NUM_LOUVERS, InternalMotionState.STATIONARY.name, dtype=object
        )
        self.target_state = np.full(
            NUM_LOUVERS, InternalMotionState.STATIONARY.name, dtype=object
        )

    async def evaluate_state(self, current_tai: float) -> None:
        """Evaluate the state and perform a state transition if necessary.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.current_tai = current_tai
        for index in range(NUM_LOUVERS):
            target_state = self.target_state[index]
            match target_state:
                case MotionState.CLOSED.name:
                    await self.handle_closed_or_open(index)
                case MotionState.OPEN.name:
                    await self.handle_closed_or_open(index)
                case MotionState.STOPPED.name:
                    await self.handle_stopped(index)
                case InternalMotionState.STATIONARY.name:
                    await self.handle_stationary(index)
                case _:
                    # Not a valid state, so empty.
                    pass

    async def handle_closed_or_open(self, index: int) -> None:
        state = self.current_state[index]
        match state:
            case InternalMotionState.STATIONARY.name:
                self.current_state[index] = MotionState.ENABLING_MOTOR_POWER.name
            case MotionState.ENABLING_MOTOR_POWER.name:
                self.current_state[index] = MotionState.MOTOR_POWER_ON.name
            case MotionState.MOTOR_POWER_ON.name:
                self.current_state[index] = MotionState.GO_NORMAL.name
            case MotionState.GO_NORMAL.name:
                self.current_state[index] = MotionState.DISENGAGING_BRAKES.name
            case MotionState.DISENGAGING_BRAKES.name:
                self.current_state[index] = MotionState.BRAKES_DISENGAGED.name
            case MotionState.BRAKES_DISENGAGED.name:
                self.current_state[index] = MotionState.MOVING.name
            case MotionState.MOVING.name:
                await self.handle_moving(index)
            case MotionState.STOPPING.name:
                self.current_state[index] = MotionState.STOPPED.name
            case MotionState.STOPPED.name:
                await self.handle_stopped(index)

    async def handle_stopped(self, index: int) -> None:
        intermediate_state = self.start_state[index]
        target_state = self.target_state[index]
        if target_state == InternalMotionState.STATIONARY.name:
            self.current_state[index] = MotionState.ENGAGING_BRAKES.name
        elif target_state in [MotionState.CLOSED.name, MotionState.OPEN.name]:
            if intermediate_state == InternalMotionState.STATIONARY.name:
                self.start_state[index] = target_state
                self.current_state[index] = MotionState.STOPPED.name
            elif intermediate_state != target_state:
                self.current_state[index] = MotionState.MOVING.name

    async def handle_stationary(self, index: int) -> None:
        state: MotionState | InternalMotionState = self.current_state[index]
        match state:
            case MotionState.STOPPED.name:
                await self.handle_stopped(index)
            case MotionState.ENGAGING_BRAKES.name:
                self.current_state[index] = MotionState.BRAKES_ENGAGED.name
            case MotionState.BRAKES_ENGAGED.name:
                self.current_state[index] = MotionState.GO_STATIONARY.name
            case MotionState.GO_STATIONARY.name:
                self.current_state[index] = MotionState.DISABLING_MOTOR_POWER.name
            case MotionState.DISABLING_MOTOR_POWER.name:
                self.current_state[index] = MotionState.MOTOR_POWER_OFF.name
            case MotionState.MOTOR_POWER_OFF.name:
                self.current_state[index] = InternalMotionState.STATIONARY.name
            case InternalMotionState.STATIONARY.name:
                self.start_state[index] = InternalMotionState.STATIONARY.name

    async def handle_moving(self, index: int) -> None:
        time_needed = (
            abs(self.position_commanded[index] - self.start_position[index])
            / MOTION_VELOCITY
        )
        time_so_far = self.current_tai - self.command_time_tai
        time_frac = 1.0
        if not np.isclose(time_needed, 0.0):
            time_frac = time_so_far / time_needed
        if time_frac >= 1.0:
            self.position_actual[index] = self.position_commanded[index]
            self.current_state[index] = MotionState.STOPPING.name
        else:
            distance = self.position_commanded[index] - self.start_position[index]
            self.position_actual[index] = (
                self.start_position[index] + distance * time_frac
            )

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        await self.evaluate_state(current_tai)
        # Determine the current drawn by the louvers.
        for index, motion_state in enumerate(self.current_state):
            # Louver motors come in pairs of two.
            if motion_state == MotionState.MOVING.name:
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
            means closed, 180 means wide open, -1 means do not move. These
            limits are not checked.
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        self.command_time_tai = current_tai
        pos: float = 0
        for louver_id, pos in enumerate(position):
            if 0 <= pos <= 100:
                if pos > 0:
                    self.start_state[louver_id] = MotionState.OPENING.name
                    self.target_state[louver_id] = MotionState.OPEN.name
                else:
                    self.start_state[louver_id] = MotionState.CLOSING.name
                    self.target_state[louver_id] = MotionState.CLOSED.name
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
        self.start_state[:] = MotionState.CLOSING.name
        self.target_state[:] = MotionState.CLOSED.name
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

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

__all__ = [
    "ApscsStatus",
    "CLOSED_POSITION",
    "CURRENT_PER_MOTOR",
    "NUM_MOTORS_PER_SHUTTER",
    "NUM_SHUTTERS",
    "OPEN_POSITION",
    "SHUTTER_SPEED",
]

import logging
import math
import random

import numpy as np
from lsst.ts.xml.enums.MTDome import MotionState

from ..enums import InternalMotionState
from ..power_management.power_draw_constants import APS_POWER_DRAW
from .base_mock_llc import (
    DEFAULT_MESSAGES,
    DOME_VOLTAGE,
    FAULT_MESSAGES,
    BaseMockStatus,
)

NUM_SHUTTERS = 2
# The number of motors per shutter.
NUM_MOTORS_PER_SHUTTER = 2

# The shutter is 0% open.
CLOSED_POSITION = 0.0
# The shutter is 100% open.
OPEN_POSITION = 100.0
# The shutter speed (%/s). This is an assumed value such that the shutter opens
# or closes in 10 seconds.
SHUTTER_SPEED = 10.0
# The motors jitter a bit and this defines the jitter range.
POSITION_JITTER = 2.5e-7

# Current per motor drawn by the Aperture Shutter [A].
CURRENT_PER_MOTOR = (
    APS_POWER_DRAW / NUM_SHUTTERS / NUM_MOTORS_PER_SHUTTER / DOME_VOLTAGE
)


def get_duration(start_position: float, end_position: float, max_speed: float) -> float:
    """Determines the duration of the move using the distance of the move
    and the maximum speed, or zero in case of a crawl.

    Parameters
    ----------
    start_position : `float`
        The start position [%].
    end_position : `float`
        The end position [%].
    max_speed : `float`
        The maximum speed [%/s].

    Returns
    -------
    duration : `float`
        The duration of the move [s].
    """
    duration = math.fabs(end_position - start_position) / max_speed
    return duration


class ApscsStatus(BaseMockStatus):
    """Represents the status of the Aperture Shutter Control System in
    simulation mode.

    Parameters
    ----------
    start_tai: `float`
        The TAI time, unix seconds, at the time at which this class is
        instantiated.  To model the real dome, this should be the current time.
        However, for unit tests it can be convenient to use other values.
    """

    def __init__(self, start_tai: float) -> None:
        super().__init__()
        self.log = logging.getLogger("MockApscsStatus")

        # Variables for the motion of the mock Aperture Shutter.
        self.start_position = np.zeros(NUM_SHUTTERS, dtype=float)
        self.start_tai = np.zeros(NUM_SHUTTERS, dtype=float)
        self.end_tai = np.zeros(NUM_SHUTTERS, dtype=float)

        # Variables holding the status of the mock Aperture Shutter.
        self.messages = DEFAULT_MESSAGES
        self.position_actual = np.zeros(NUM_SHUTTERS, dtype=float)
        self.position_commanded = np.zeros(NUM_SHUTTERS, dtype=float)
        self.drive_torque_actual = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.drive_torque_commanded = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.drive_current_actual = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.drive_temperature = np.full(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, 20.0, dtype=float
        )
        self.resolver_head_raw = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.resolver_head_calibrated = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.power_draw = 0.0

        # State machine related attributes.
        self.current_state = [MotionState.CLOSED.name, MotionState.CLOSED.name]
        self.start_state = [MotionState.CLOSED.name, MotionState.CLOSED.name]
        self.target_state = [MotionState.CLOSED.name, MotionState.CLOSED.name]

        # Error state related attributes.
        self.drives_in_error_state = [[False] * NUM_MOTORS_PER_SHUTTER] * NUM_SHUTTERS

    async def evaluate_state(self, current_tai: float, shutter_id: int) -> None:
        """Evaluate the state and perform a state transition if necessary.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        shutter_id : `int`
            The shutter id.
        """
        match self.target_state[shutter_id]:
            case (
                MotionState.OPEN.name
                | MotionState.CLOSED.name
                | MotionState.UNDETERMINED.name
                | InternalMotionState.STATIONARY.name
            ):
                await self._handle_open_or_close_or_stationary(current_tai, shutter_id)
            case MotionState.STOPPED.name:
                await self._handle_stopped(shutter_id)
            case _:
                await self._warn_invalid_state(shutter_id)

    async def _warn_invalid_state(self, shutter_id: int) -> None:
        self.log.warning(
            f"Not handling invalid target state {self.target_state[shutter_id]}"
        )

    async def _handle_open_or_close_or_stationary(
        self, current_tai: float, shutter_id: int
    ) -> None:
        match self.current_state[shutter_id]:
            case InternalMotionState.STATIONARY.name:
                await self._handle_stationary(shutter_id)
            case MotionState.CLOSED.name:
                await self._handle_closed(shutter_id)
            case MotionState.OPEN.name:
                await self._handle_open(shutter_id)
            case MotionState.LP_DISENGAGING.name:
                self.current_state[shutter_id] = MotionState.LP_DISENGAGED.name
            case MotionState.LP_DISENGAGED.name:
                self.current_state[shutter_id] = MotionState.ENABLING_MOTOR_POWER.name
            case MotionState.ENABLING_MOTOR_POWER.name:
                self.current_state[shutter_id] = MotionState.MOTOR_POWER_ON.name
            case MotionState.MOTOR_POWER_ON.name:
                self.current_state[shutter_id] = MotionState.GO_NORMAL.name
            case MotionState.GO_NORMAL.name:
                self.current_state[shutter_id] = MotionState.DISENGAGING_BRAKES.name
            case MotionState.DISENGAGING_BRAKES.name:
                self.current_state[shutter_id] = MotionState.BRAKES_DISENGAGED.name
            case MotionState.BRAKES_DISENGAGED.name:
                await self._handle_brakes_disengaged(shutter_id)
            case MotionState.OPENING.name:
                await self._handle_opening_or_closing(current_tai, shutter_id)
            case MotionState.PROXIMITY_OPEN_LS_ENGAGED.name:
                await self._handle_proximity_open_ls_engaged(shutter_id)
            case MotionState.FINAL_UP_OPEN_LS_ENGAGED.name:
                await self._handle_final_up_open_ls_engaged(shutter_id)
            case MotionState.FINAL_DOWN_OPEN_LS_ENGAGED.name:
                self.current_state[shutter_id] = MotionState.STOPPING.name
            case MotionState.CLOSING.name:
                await self._handle_opening_or_closing(current_tai, shutter_id)
            case MotionState.PROXIMITY_CLOSED_LS_ENGAGED.name:
                await self._handle_proximity_closed_ls_engaged(shutter_id)
            case MotionState.FINAL_UP_CLOSE_LS_ENGAGED.name:
                await self._handle_final_up_close_ls_engaged(shutter_id)
            case MotionState.FINAL_DOWN_CLOSE_LS_ENGAGED.name:
                self.current_state[shutter_id] = MotionState.STOPPING.name
            case MotionState.STOPPING.name:
                self.current_state[shutter_id] = MotionState.STOPPED.name
            case MotionState.STOPPED.name:
                await self._handle_stopped(shutter_id)
            case MotionState.ENGAGING_BRAKES.name:
                self.current_state[shutter_id] = MotionState.BRAKES_ENGAGED.name
            case MotionState.BRAKES_ENGAGED.name:
                self.current_state[shutter_id] = MotionState.GO_STATIONARY.name
            case MotionState.GO_STATIONARY.name:
                await self._handle_go_stationary(shutter_id)
            case MotionState.LP_ENGAGING.name:
                self.current_state[shutter_id] = MotionState.LP_ENGAGED.name
            case MotionState.LP_ENGAGED.name:
                self.current_state[shutter_id] = MotionState.DISABLING_MOTOR_POWER.name
            case MotionState.DISABLING_MOTOR_POWER.name:
                self.current_state[shutter_id] = MotionState.MOTOR_POWER_OFF.name
            case MotionState.MOTOR_POWER_OFF.name:
                await self._handle_motor_power_off(shutter_id)

    async def _handle_stationary(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] in [
            MotionState.OPENING.name,
            MotionState.CLOSING.name,
        ]:
            self.current_state[shutter_id] = MotionState.ENABLING_MOTOR_POWER.name
        else:
            await self._warn_invalid_state(shutter_id)

    async def _handle_closed(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] in [
            MotionState.OPENING.name,
            InternalMotionState.STATIONARY.name,
        ]:
            self.current_state[shutter_id] = MotionState.LP_DISENGAGING.name
        else:
            await self._warn_invalid_state(shutter_id)

    async def _handle_open(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] in [
            MotionState.CLOSING.name,
            InternalMotionState.STATIONARY.name,
        ]:
            self.current_state[shutter_id] = MotionState.LP_DISENGAGING.name
        else:
            await self._warn_invalid_state(shutter_id)

    async def _handle_opening_or_closing(
        self, current_tai: float, shutter_id: int
    ) -> None:
        if self.start_state[shutter_id] in [
            MotionState.STOPPING.name,
            MotionState.GO_STATIONARY.name,
        ]:
            self.current_state[shutter_id] = MotionState.STOPPING.name
        else:
            await self._handle_moving(current_tai, shutter_id)

    async def _handle_proximity_open_ls_engaged(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] == MotionState.STOPPING.name:
            self.current_state[shutter_id] = MotionState.STOPPING.name
        else:
            self.current_state[shutter_id] = MotionState.FINAL_UP_OPEN_LS_ENGAGED.name

    async def _handle_final_up_open_ls_engaged(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] == MotionState.STOPPING.name:
            self.current_state[shutter_id] = MotionState.STOPPING.name
        else:
            self.current_state[shutter_id] = MotionState.FINAL_DOWN_OPEN_LS_ENGAGED.name

    async def _handle_proximity_closed_ls_engaged(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] == MotionState.STOPPING.name:
            self.current_state[shutter_id] = MotionState.STOPPING.name
        else:
            self.current_state[shutter_id] = MotionState.FINAL_UP_CLOSE_LS_ENGAGED.name

    async def _handle_final_up_close_ls_engaged(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] == MotionState.STOPPING.name:
            self.current_state[shutter_id] = MotionState.STOPPING.name
        else:
            self.current_state[shutter_id] = (
                MotionState.FINAL_DOWN_CLOSE_LS_ENGAGED.name
            )

    async def _handle_brakes_disengaged(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] == MotionState.OPENING.name:
            self.current_state[shutter_id] = MotionState.OPENING.name
        elif self.start_state[shutter_id] == MotionState.CLOSING.name:
            self.current_state[shutter_id] = MotionState.CLOSING.name
        else:
            await self._warn_invalid_state(shutter_id)

    async def _handle_go_stationary(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] in [
            MotionState.OPENING.name,
            MotionState.CLOSING.name,
        ]:
            self.current_state[shutter_id] = MotionState.LP_ENGAGING.name
        else:
            self.current_state[shutter_id] = MotionState.DISABLING_MOTOR_POWER.name

    async def _handle_motor_power_off(self, shutter_id: int) -> None:
        if self.start_state[shutter_id] == MotionState.OPENING.name:
            self.start_state[shutter_id] = MotionState.OPEN.name
            self.current_state[shutter_id] = MotionState.OPEN.name
            self.target_state[shutter_id] = MotionState.OPEN.name
        elif self.start_state[shutter_id] == MotionState.CLOSING.name:
            self.start_state[shutter_id] = MotionState.CLOSED.name
            self.current_state[shutter_id] = MotionState.CLOSED.name
            self.target_state[shutter_id] = MotionState.CLOSED.name
        else:
            self.start_state[shutter_id] = InternalMotionState.STATIONARY.name
            self.current_state[shutter_id] = InternalMotionState.STATIONARY.name
            self.target_state[shutter_id] = InternalMotionState.STATIONARY.name

    async def _handle_moving(self, current_tai: float, shutter_id: int) -> None:
        if current_tai >= self.end_tai[shutter_id]:
            self.position_actual[shutter_id] = self.position_commanded[shutter_id]

            if self.start_state[shutter_id] == MotionState.OPENING.name:
                self.current_state[shutter_id] = (
                    MotionState.PROXIMITY_OPEN_LS_ENGAGED.name
                )
            elif self.start_state[shutter_id] == MotionState.CLOSING.name:
                self.current_state[shutter_id] = (
                    MotionState.PROXIMITY_CLOSED_LS_ENGAGED.name
                )
            else:
                await self._warn_invalid_state(shutter_id)
        elif current_tai < self.start_tai[shutter_id]:
            raise ValueError(
                f"TAI {current_tai} is smaller than start TAI {self.start_tai[shutter_id]}."
            )
        else:
            frac_time = (current_tai - self.start_tai[shutter_id]) / (
                self.end_tai[shutter_id] - self.start_tai[shutter_id]
            )
            distance = (
                self.position_commanded[shutter_id] - self.start_position[shutter_id]
            )
            self.position_actual[shutter_id] = (
                self.start_position[shutter_id] + distance * frac_time
            )

        # Add jitter.
        self.position_actual[shutter_id] = self.position_actual[
            shutter_id
        ] + random.uniform(-POSITION_JITTER, POSITION_JITTER)

    async def _handle_stopped(self, shutter_id: int) -> None:
        if self.current_state[shutter_id] == MotionState.STOPPING.name:
            self.current_state[shutter_id] = MotionState.STOPPED.name
        elif self.current_state[
            shutter_id
        ] == MotionState.STOPPING.name and self.target_state[shutter_id] in [
            MotionState.OPENING.name,
            MotionState.CLOSING.name,
            MotionState.GO_STATIONARY.name,
        ]:
            self.current_state[shutter_id] = MotionState.ENGAGING_BRAKES.name

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        # Loop over all doors to collect their states.
        for shutter_id in range(NUM_SHUTTERS):
            await self.evaluate_state(current_tai, shutter_id)

            # Determine the current drawn by the aperture shutter.
            if self.current_state[shutter_id] in [
                MotionState.OPENING.name,
                MotionState.CLOSING.name,
            ]:
                self.drive_current_actual[
                    shutter_id
                    * NUM_MOTORS_PER_SHUTTER : (shutter_id + 1)
                    * NUM_MOTORS_PER_SHUTTER
                ] = CURRENT_PER_MOTOR
                self.power_draw = APS_POWER_DRAW
            else:
                self.drive_current_actual[
                    shutter_id
                    * NUM_MOTORS_PER_SHUTTER : (shutter_id + 1)
                    * NUM_MOTORS_PER_SHUTTER
                ] = 0.0
                self.power_draw = 0.0
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": self.current_state,
                "operationalMode": self.operational_mode.name,
            },
            "positionActual": self.position_actual.tolist(),
            "positionCommanded": self.position_commanded.tolist(),
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

    async def openShutter(self, start_tai: float) -> float:
        """Open the shutter.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        durations = [0.0, 0.0]
        for shutter_id in range(NUM_SHUTTERS):
            if not math.isclose(self.position_actual[shutter_id], OPEN_POSITION):
                self.start_position[shutter_id] = self.position_actual[shutter_id]
                self.position_commanded[shutter_id] = OPEN_POSITION
                self.start_state[shutter_id] = MotionState.OPENING.name
                self.target_state[shutter_id] = MotionState.OPEN.name
                self.start_tai[shutter_id] = start_tai
                durations[shutter_id] = get_duration(
                    start_position=self.position_actual[shutter_id],
                    end_position=OPEN_POSITION,
                    max_speed=SHUTTER_SPEED,
                )
                self.end_tai[shutter_id] = (
                    durations[shutter_id] + self.start_tai[shutter_id]
                )
        return max(durations)

    async def closeShutter(self, start_tai: float) -> float:
        """Close the shutter.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        durations = [0.0, 0.0]
        for shutter_id in range(NUM_SHUTTERS):
            if not math.isclose(self.position_actual[shutter_id], CLOSED_POSITION):
                self.start_position[shutter_id] = self.position_actual[shutter_id]
                self.position_commanded[shutter_id] = CLOSED_POSITION
                self.start_state[shutter_id] = MotionState.CLOSING.name
                self.target_state[shutter_id] = MotionState.CLOSED.name
                self.start_tai[shutter_id] = start_tai
                durations[shutter_id] = get_duration(
                    start_position=self.position_actual[shutter_id],
                    end_position=CLOSED_POSITION,
                    max_speed=SHUTTER_SPEED,
                )
                self.end_tai[shutter_id] = (
                    durations[shutter_id] + self.start_tai[shutter_id]
                )
        return max(durations)

    async def stopShutter(self, start_tai: float) -> float:
        """Stop all motion of the shutter.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        for shutter_id in range(NUM_SHUTTERS):
            if self.current_state[shutter_id] not in [
                MotionState.STOPPED.name,
                MotionState.STOPPING.name,
            ]:
                await self._handle_moving(start_tai, shutter_id)
                self.start_state[shutter_id] = MotionState.STOPPING.name
                self.current_state[shutter_id] = MotionState.STOPPING.name
                self.target_state[shutter_id] = MotionState.STOPPED.name
                self.start_tai[shutter_id] = start_tai
                self.start_position[shutter_id] = self.position_actual[shutter_id]
                self.end_tai[shutter_id] = start_tai
        return 0.0

    async def go_stationary(self, start_tai: float) -> float:
        """Stop shutter motion and engage the brakes.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        durations = [0.0, 0.0]
        for shutter_id in range(NUM_SHUTTERS):
            if self.current_state[shutter_id] != InternalMotionState.STATIONARY.name:
                await self._handle_moving(start_tai, shutter_id)
                self.start_position[shutter_id] = self.position_actual[shutter_id]
                self.start_state[shutter_id] = MotionState.GO_STATIONARY.name
                self.target_state[shutter_id] = InternalMotionState.STATIONARY.name
                self.start_tai[shutter_id] = start_tai
                durations[shutter_id] = get_duration(
                    start_position=self.position_actual[shutter_id],
                    end_position=OPEN_POSITION,
                    max_speed=SHUTTER_SPEED,
                )
                self.end_tai[shutter_id] = (
                    durations[shutter_id] + self.start_tai[shutter_id]
                )
        duration = max(durations)
        return duration

    async def search_zero_shutter(self, start_tai: float) -> float:
        """Search the zero position of the Aperture Shutter, which is the
        closed position. This is necessary in case the ApSCS (Aperture Shutter
        Control system) was shutdown with the Aperture Shutter not fully open
        or fully closed. For now `closeShutter` simply is called but this may
        change.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        return await self.closeShutter(start_tai)

    async def exit_fault(self, start_tai: float) -> float:
        """Clear the fault state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        for shutter_id in range(NUM_SHUTTERS):
            if any(self.drives_in_error_state[shutter_id]):
                raise RuntimeError(
                    "Make sure to reset drives before exiting from fault."
                )

        for shutter_id in range(NUM_SHUTTERS):
            self.start_position[shutter_id] = self.position_actual[shutter_id]
            if self.current_state[shutter_id] == MotionState.ERROR.name:
                self.start_state[shutter_id] = InternalMotionState.STATIONARY.name
                self.current_state[shutter_id] = InternalMotionState.STATIONARY.name
                self.target_state[shutter_id] = InternalMotionState.STATIONARY.name
                self.start_tai = np.full(NUM_SHUTTERS, start_tai, dtype=float)
                self.start_tai[shutter_id] = start_tai
                self.end_tai[shutter_id] = start_tai
        self.messages = DEFAULT_MESSAGES
        return 0.0

    async def reset_drives_shutter(self, start_tai: float, reset: list[int]) -> float:
        """Reset one or more Aperture Shutter drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        reset: array of int
            Desired reset action to execute on each Aperture Shutter drive: 0
            means don't reset, 1 means reset.

        Returns
        -------
        `float`
            The expected duration of the command [s].

        Raises
        ------
        ValueError
            If the 'reset' parameter has the wrong length.

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        if len(reset) != NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER:
            raise ValueError(
                f"The length of 'reset' should be {NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER} "
                f"but is {len(reset)}."
            )
        for shutter_id in range(NUM_SHUTTERS):
            for i, val in enumerate(
                reset[
                    shutter_id * NUM_SHUTTERS : shutter_id * NUM_SHUTTERS
                    + NUM_MOTORS_PER_SHUTTER
                ]
            ):
                if val == 1:
                    self.drives_in_error_state[shutter_id][i] = False
            self.start_tai[shutter_id] = start_tai
            self.end_tai[shutter_id] = start_tai
        return 0.0

    async def set_fault(self, start_tai: float, drives_in_error: list[int]) -> None:
        """Set the MotionState of ApSCS to fault and set the drives in
        drives_in_error to error.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        drives_in_error : array of int
            Desired error action to execute on each Shutter drive: 0 means
            don't set to error, 1 means set to error. There should be 4 error
            actions and that is not checked.

        Raises
        ------
        ValueError
            If the 'drives_in_error' parameter has the wrong length.

        Notes
        -----
        This function is not mapped to a command that MockMTDomeController can
        receive. It is intended to be set by unit test cases.
        """
        if len(drives_in_error) != NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER:
            raise ValueError(
                f"The length of 'drives_in_error' should be {NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER}"
                f" but is {len(drives_in_error)}."
            )
        for shutter_id in range(NUM_SHUTTERS):
            await self._handle_moving(start_tai, shutter_id)
            for i, val in enumerate(
                drives_in_error[
                    shutter_id * NUM_SHUTTERS : shutter_id * NUM_SHUTTERS
                    + NUM_MOTORS_PER_SHUTTER
                ]
            ):
                self.drives_in_error_state[shutter_id][i] = val == 1
            self.start_state[shutter_id] = MotionState.ERROR.name
            self.current_state[shutter_id] = MotionState.ERROR.name
            self.target_state[shutter_id] = MotionState.ERROR.name
        self.messages = FAULT_MESSAGES

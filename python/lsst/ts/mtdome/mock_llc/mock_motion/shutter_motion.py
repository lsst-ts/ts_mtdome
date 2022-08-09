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

__all__ = [
    "ShutterMotion",
    "CLOSED_POSITION",
    "NUM_MOTORS_PER_SHUTTER",
    "OPEN_POSITION",
    "SHUTTER_SPEED",
]

import logging
import math

from ...enums import LlcMotionState
from .base_llc_motion import BaseLlcMotion

# The number of motors per shutter.
NUM_MOTORS_PER_SHUTTER = 2

# The shutter is 0% open.
CLOSED_POSITION = 0.0
# The shutter is 100% open.
OPEN_POSITION = 100.0
# The shutter speed (%/s). This is an assumed value such that the shutter opens
# or closes in 10 seconds.
SHUTTER_SPEED = 10.0


class ShutterMotion(BaseLlcMotion):
    """Simulator for one door (of two) of the aperture shutter motion of the
    MTDome.

    Parameters
    ----------
    start_position: `float`
        The initial position [%].
    start_tai: `float`
        The current TAI time, unix seconds. To model the real dome, this should
        be the current time. However, for unit tests it can be convenient to
        use other values.
    """

    def __init__(
        self,
        start_position: float,
        start_tai: float,
    ):
        super().__init__(
            start_position=start_position,
            min_position=CLOSED_POSITION,
            max_position=OPEN_POSITION,
            max_speed=SHUTTER_SPEED,
            start_tai=start_tai,
        )
        self.log = logging.getLogger("ShutterMotion")
        # Keep track of being in error state or not.
        self.motion_state_in_error = False
        # Keep track of which drives are in error state.
        self.drives_in_error_state = [False] * NUM_MOTORS_PER_SHUTTER
        # Keep track of when motion state went into ERROR
        self._error_start_tai = 0.0
        # Keep track of the position at the moment that ERROR state starts.
        self._error_state_position = 0.0

    def _get_duration(self) -> float:
        duration = math.fabs(
            (self._end_position - self._start_position) / SHUTTER_SPEED
        )
        return duration

    def set_target_position_and_velocity(
        self,
        start_tai: float,
        end_position: float,
        crawl_velocity: float = 0.0,
        motion_state: LlcMotionState = LlcMotionState.MOVING,
    ) -> float:
        if crawl_velocity != 0.0:
            raise ValueError(f"crawl_velocity={crawl_velocity} must be 0.0!")
        if not self._min_position <= end_position <= self._max_position:
            raise ValueError(
                f"The target position {end_position} is outside of the "
                f"range [{self._min_position, self._max_position}]"
            )

        self._commanded_motion_state = motion_state
        self._start_tai = start_tai
        self._end_position = end_position
        duration = self._get_duration()
        self._end_tai = self._start_tai + duration
        return duration

    def get_position_velocity_and_motion_state(
        self, tai: float
    ) -> tuple[float, float, LlcMotionState]:
        """Computes the position and `LlcMotionState` for the given TAI time.

        Parameters
        ----------
        tai: `float`
            The TAI time, unix seconds, for which to compute the position. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.

        Returns
        -------
        position: `float`
            The position [%] at the given TAI time, taking the move velocity
            into account.
        velocity: `float`
            The velocity [%/s] at the given TAI time.
        motion_state: `LlcMotionState`
            The LlcMotionState of the shutter door at the given TAI time.
        """

        if self.motion_state_in_error:
            tai = self._error_start_tai

        if tai >= self._end_tai:
            if self._commanded_motion_state in [
                LlcMotionState.STOPPED,
                LlcMotionState.MOVING,
            ]:
                motion_state = LlcMotionState.STOPPED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state == LlcMotionState.STATIONARY:
                motion_state = LlcMotionState.STATIONARY
                position = self._end_position
                velocity = 0.0
            else:
                raise ValueError(
                    f"Encountered unexpected commanded motion state={self._commanded_motion_state}"
                )
        elif tai < self._start_tai:
            raise ValueError(
                f"Encountered TAI {tai} which is smaller than start TAI {self._start_tai}"
            )
        else:
            frac_time = (tai - self._start_tai) / (self._end_tai - self._start_tai)
            distance = self._end_position - self._start_position
            position = self._start_position + distance * frac_time
            velocity = SHUTTER_SPEED
            if distance < 0.0:
                velocity = -SHUTTER_SPEED
            if self._commanded_motion_state == LlcMotionState.STOPPED:
                motion_state = LlcMotionState.STOPPED
                velocity = 0.0
            elif self._commanded_motion_state == LlcMotionState.STATIONARY:
                motion_state = LlcMotionState.STATIONARY
                velocity = 0.0
            else:
                motion_state = LlcMotionState.MOVING

        if self.motion_state_in_error:
            velocity = 0.0
            motion_state = LlcMotionState.ERROR

        return position, velocity, motion_state

    def stop(self, start_tai: float) -> float:
        """Stops the current motion.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        """
        position, velocity, motion_state = self.get_position_velocity_and_motion_state(
            tai=start_tai
        )
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = position
        self._commanded_motion_state = LlcMotionState.STOPPED
        return 0.0

    def go_stationary(self, start_tai: float) -> float:
        """Go to stationary state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        """
        position, velocity, motion_state = self.get_position_velocity_and_motion_state(
            tai=start_tai
        )
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = position
        self._commanded_motion_state = LlcMotionState.STATIONARY
        return 0.0

    def exit_fault(self, start_tai: float) -> float:
        """Clear the fault state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command.
        """
        if True in self.drives_in_error_state:
            raise RuntimeError("Make sure to reset drives before exiting from fault.")

        if self.motion_state_in_error:
            (
                position,
                velocity,
                motion_state,
            ) = self.get_position_velocity_and_motion_state(tai=start_tai)
            self._start_tai = start_tai
            self._start_position = position
            self._end_position = position
            self.motion_state_in_error = False
            self._commanded_motion_state = LlcMotionState.STATIONARY
        return 0.0

    def reset_drives_shutter(self, start_tai: float, reset: list[int]) -> float:
        """Reset one or more Shutter drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        reset: array of int
            Desired reset action to execute on each Shutter drive: 0 means
            don't reset, 1 means reset.

        Returns
        -------
        `float`
            The expected duration of the command.

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        for i, val in enumerate(reset):
            if val == 1:
                self.drives_in_error_state[i] = False
        return 0.0

    def set_fault(self, start_tai: float, drives_in_error: list[int]) -> None:
        """Set the LlcMotionState of ApSCS to fault and set the drives in
        drives_in_error to error.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        drives_in_error : array of int
            Desired error action to execute on each Shutter drive: 0 means
            don't set to error, 1 means set to error.

        Notes
        -----
        This function is not mapped to a command that MockMTDomeController can
        receive. It is intended to be set by unit test cases.
        """
        position, velocity, motion_state = self.get_position_velocity_and_motion_state(
            tai=start_tai
        )
        self._error_state_position = position
        self.motion_state_in_error = True
        self._error_start_tai = start_tai
        for i, val in enumerate(drives_in_error):
            if val == 1:
                self.drives_in_error_state[i] = True

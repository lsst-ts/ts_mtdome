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

import math
from abc import ABC, abstractmethod

from lsst.ts import utils
from lsst.ts.idl.enums.MTDome import MotionState

from ...enums import InternalMotionState


class BaseLlcMotion(ABC):
    def __init__(
        self,
        start_position: float,
        min_position: float,
        max_position: float,
        max_speed: float,
        start_tai: float,
    ):
        # This defines the start position of a move or a crawl.
        self._start_position = start_position
        # This defines the end position of the move, after which all motion
        # will stop. Ignored in case of a crawl command.
        self._end_position = start_position
        # This defines the minimum allowed position.
        self._min_position = min_position
        # This defines the maximum allowed position.
        self._max_position = max_position
        # This is not a constant but can be configured by the MTDome CSC, which
        # is why it is a parameter.
        self._max_speed = max_speed
        # Keep track of the current motion state.
        self._current_motion_state = MotionState.PARKED
        # The commanded MotionState, against which the computed
        # MotionState will be compared. By default the elevation motion
        # starts in STOPPED state. The MotionState only changes when a new
        # command is received.
        self._commanded_motion_state = MotionState.STOPPED
        # This defines the TAI time, unix seconds, at which a move or crawl
        # will start. To model the real dome, this should be the current time.
        # However, for unit tests it can be convenient to use other values.
        self._start_tai = start_tai
        # This defines the TAI time, unix seconds, at which the move will end,
        # after which all motion is stopped. Ignored in case of a crawl
        # command. To model the real dome, this should be the current time.
        # However, for unit tests it can be convenient to use other values.
        self._end_tai = 0.0
        # Keep track of being in error state or not.
        self.motion_state_in_error = False
        # Keep track of which drives are in error state. For this base class
        # this is just a dummy value to make the code work. Each implementing
        # subclass will have to define this properly itself.
        self.drives_in_error_state = [False]
        # Keep track of when motion state went into ERROR
        self._error_start_tai = 0.0
        # Keep track of the position at the moment that ERROR state starts.
        self._error_state_position = 0.0

    def base_set_target_position_and_velocity(
        self,
        start_tai: float,
        end_position: float,
        motion_state: MotionState,
    ) -> float:
        """Sets the end_position and crawl_velocity and returns the duration of
        the move.

        No aceleration is taken into account.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        end_position: `float`
            The target position.
        motion_state: `MotionState`
            MOVING or CRAWLING. The value is not checked.

        Returns
        -------
        duration: `float`
            The duration of the move.

        Raises
        ------
        ValueError
            If the target position falls outside the range
            [min position, max position] or if abs(crawl_velocity) > max_speed.

        """
        if motion_state not in [MotionState.MOVING, MotionState.CRAWLING]:
            raise ValueError(f"{motion_state=!r} should be MOVING or CRAWLING.")

        if (
            motion_state == MotionState.MOVING
            and not self._min_position <= end_position <= self._max_position
        ):
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

    def _get_distance(self) -> float:
        """Determines the smallest distance [rad] between the initial and
        target positions assuming motion around a circle.

        Returns
        -------
        distance: `float`
            The smallest distance between the initial and target positions.

        Notes
        -----
        If "_start_position" and "_end_position" are not in radians, this
        method should be overridden.
        """
        distance = utils.angle_diff(
            math.degrees(self._end_position), math.degrees(self._start_position)
        ).rad
        return distance

    def _get_duration(self) -> float:
        """Determines the duration of the move using the distance of the move
        and the maximum speed, or zero in case of a crawl.

        Returns
        -------
        duration: `float`
            The duration of the move, or zero in case of a crawl.
        """
        duration = math.fabs(self._get_distance()) / self._max_speed
        return duration

    @abstractmethod
    def get_position_velocity_and_motion_state(
        self, tai: float
    ) -> tuple[float, float, MotionState]:
        pass

    def stop(self, start_tai: float) -> float:
        """Stop the current motion.

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
        self._current_motion_state = motion_state
        self._commanded_motion_state = MotionState.STOPPED
        self._end_tai = self._start_tai + self._get_duration()
        return self._end_tai - start_tai

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
        self._commanded_motion_state = InternalMotionState.STATIONARY
        self._end_tai = self._start_tai + self._get_duration()
        return self._end_tai - start_tai

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
            self._start_position = self._error_state_position
            self._end_position = self._error_state_position
            self._current_motion_state = InternalMotionState.STATIONARY
            self._commanded_motion_state = InternalMotionState.STATIONARY
            self.motion_state_in_error = False
            self._error_start_tai = 0.0
            self._error_state_position = 0.0
        return 0.0

    def set_fault(self, start_tai: float, drives_in_error: list[int]) -> None:
        """Set the MotionState of AMCS to fault and set the drives in
        drives_in_error to error.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        drives_in_error : array of int
            Desired error action to execute on each AZ drive: 0 means don't
            set to error, 1 means set to error.

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

    def reset_drives(self, start_tai: float, reset: list[int]) -> float:
        """Reset one or more drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        reset: array of int
            Desired reset action to execute on each drive: 0 means don't reset,
            1 means reset.

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

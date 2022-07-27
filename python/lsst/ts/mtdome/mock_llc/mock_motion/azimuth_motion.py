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

__all__ = ["AzimuthMotion"]

import logging
import math
import typing

from .base_llc_motion import BaseLlcMotion
from ...enums import LlcMotionState, IntermediateState
from lsst.ts import utils

# The mocked duration of an intermediate state.
INTERMEDIATE_STATE_DURATION = 0.5
# The mocked duration for any intermdediate state involving the inflatable
# seal.
INFLATABLE_SEAL_DURATION = 1.0

STATE_SEQUENCE_START_MOTORS = [
    (IntermediateState.DEFLATING, INFLATABLE_SEAL_DURATION),
    (IntermediateState.DEFLATED, INFLATABLE_SEAL_DURATION),
    (IntermediateState.STARTING_MOTOR_COOLING, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.MOTOR_COOLING_ON, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.ENABLING_MOTOR_POWER, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.MOTOR_POWER_ON, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.GO_NORMAL, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.DISENGAGING_BRAKES, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.BRAKES_DISENGAGED, INTERMEDIATE_STATE_DURATION),
]
STATE_SEQUENCE_STOP_MOTORS = [
    (IntermediateState.ENGAGING_BRAKES, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.BRAKES_ENGAGED, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.GO_STATIONARY, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.DISABLING_MOTOR_POWER, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.MOTOR_POWER_OFF, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.STOPPING_MOTOR_COOLING, INTERMEDIATE_STATE_DURATION),
    (IntermediateState.MOTOR_COOLING_OFF, INTERMEDIATE_STATE_DURATION),
]

# Dict of allowed motion state transitions and the intermediary states between
# those motion states, if applicable.
STATE_TRANSITIONS: dict[
    typing.Tuple[LlcMotionState, LlcMotionState],
    list[typing.Tuple[IntermediateState, float]],
] = {
    (LlcMotionState.PARKED, LlcMotionState.MOVING): STATE_SEQUENCE_START_MOTORS,
    (LlcMotionState.PARKED, LlcMotionState.CRAWLING): STATE_SEQUENCE_START_MOTORS,
    (LlcMotionState.MOVING, LlcMotionState.CRAWLING): [],
    (LlcMotionState.CRAWLING, LlcMotionState.MOVING): [],
    (LlcMotionState.CRAWLING, LlcMotionState.STOPPED): [],
    (LlcMotionState.MOVING, LlcMotionState.CRAWLING): [],
    (LlcMotionState.MOVING, LlcMotionState.STOPPED): [],
    (LlcMotionState.CRAWLING, LlcMotionState.MOVING): [],
    (LlcMotionState.MOVING, LlcMotionState.PARKED): STATE_SEQUENCE_STOP_MOTORS,
    (LlcMotionState.CRAWLING, LlcMotionState.PARKED): STATE_SEQUENCE_STOP_MOTORS,
    (LlcMotionState.STOPPED, LlcMotionState.PARKED): STATE_SEQUENCE_STOP_MOTORS,
    (LlcMotionState.MOVING, LlcMotionState.STATIONARY): STATE_SEQUENCE_STOP_MOTORS,
    (LlcMotionState.CRAWLING, LlcMotionState.STATIONARY): STATE_SEQUENCE_STOP_MOTORS,
    (LlcMotionState.STOPPED, LlcMotionState.STATIONARY): STATE_SEQUENCE_STOP_MOTORS,
    (LlcMotionState.STOPPED, LlcMotionState.MOVING): [],
}

CALIBRATE_AZ_ALLOWED_STATES = [
    LlcMotionState.PARKED,
    LlcMotionState.STATIONARY,
    LlcMotionState.STOPPED,
]


class AzimuthMotion(BaseLlcMotion):
    """Simulator for the azimuth motion of the MTDome.

    Parameters
    ----------
    start_position: `float`
        The start position [rad] of the move.
    max_speed: `float`
        The maximum allowed speed [rad/s].
    start_tai: `float`
        The TAI time, unix seconds, of the start of the move. This also needs
        to be set in the constructor so this class knows what the TAI time
        currently is.

    Notes
    -----
    This simulator can either move the dome to a target position at maximum
    speed and start crawling from there with the specified crawl velocity, or
    crawl at the specified velocity. It handles the 0/2pi radians boundary.
    When either moving or crawling, a new move or handle command is handled,
    the azimuth motion/crawl can be stopped and the dome can be parked.
    """

    def __init__(
        self, start_position: float, max_speed: float, start_tai: float
    ) -> None:
        super().__init__(
            start_position=start_position,
            min_position=0.0,
            max_position=2.0 * math.pi,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        self.log = logging.getLogger("AzimuthMotion")
        # The azimuth motion always starts in PARKED state.
        self._commanded_motion_state = LlcMotionState.PARKED
        # Keep track of the motion state where we came from.
        self._current_motion_state = LlcMotionState.PARKED
        # Keep track of being in error state or not.
        self.motion_state_in_error = False
        # Keep track of which drives are in error state.
        self.drives_in_error_state = [False] * 5
        # Keep track of when motion state went into ERROR
        self._error_start_tai = 0.0
        # Keep track of the additional duration needed for the dome to start
        # moving when PARKED or STATIONARY for computations of the position and
        # velocity when MOVING or CRAWLING
        self._computed_additional_duration = 0.0
        # Keep track of the position at the moment that ERROR state starts.
        self._error_state_position = 0.0

    def _get_additional_duration(self) -> float:
        if (
            self._current_motion_state == LlcMotionState.ERROR
            or self._current_motion_state == self._commanded_motion_state
        ):
            return 0.0

        intermediate_state_list = STATE_TRANSITIONS[
            (self._current_motion_state, self._commanded_motion_state)
        ]
        additional_duration = sum([t[1] for t in intermediate_state_list])
        return additional_duration

    def _get_duration(self) -> float:
        default_duration = super()._get_duration()
        additional_duration = self._get_additional_duration()
        return default_duration + additional_duration

    def set_target_position_and_velocity(
        self,
        start_tai: float,
        end_position: float,
        crawl_velocity: float,
        motion_state: LlcMotionState,
    ) -> float:
        """Sets the end_position and crawl velocity and returns the duration
        of the move.

        No aceleration is taken into account. The time taken by crawling is not
        taken into account either.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        end_position: `float`
            The end position [rad] of the move. Ignored if `do_move` is False.
        crawl_velocity: `float`
            The crawl_velocity [rad/s] at which to crawl once the move is done.
        motion_state: `LlcMotionState`
            MOVING or CRAWLING. The value is checked.

        Returns
        -------
        duration: `float`
            The duration [s] of the move.

        Raises
        ------
        ValueError
            If abs(crawl_velocity) > max_speed.
        ValueError
            if LlcMotionState is not MOVING or CRAWLING.

        """
        if math.fabs(crawl_velocity) > self._max_speed:
            raise ValueError(
                f"The target crawl speed {math.fabs(crawl_velocity)} is larger"
                f" than the max speed {self._max_speed}."
            )
        if motion_state not in [LlcMotionState.MOVING, LlcMotionState.CRAWLING]:
            raise ValueError("motion_speed should be MOVING or CRAWLING.")

        self._commanded_motion_state = motion_state
        self._start_tai = start_tai
        self._end_position = end_position
        self._crawl_velocity = crawl_velocity
        duration = self._get_duration()
        self._end_tai = self._start_tai + duration
        return duration

    def get_position_velocity_and_motion_state(
        self, tai: float
    ) -> typing.Tuple[float, float, LlcMotionState]:
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
            The position [rad] at the given TAI time, taking both the move
            (optional) and crawl velocities into account.
        velocity: `float`
            The velocity [rad/s] at the given TAI time.
        motion_state: `LlcMotionState`
            The LlcMotionState at the given TAI time.
        """

        if self.motion_state_in_error:
            tai = self._error_start_tai

        additional_duration = self._get_additional_duration()
        distance = self._get_distance()
        end_tai = self._end_tai
        if self._current_motion_state in [
            LlcMotionState.MOVING,
            LlcMotionState.CRAWLING,
            LlcMotionState.STOPPED,
        ] and self._commanded_motion_state in [
            LlcMotionState.PARKED,
            LlcMotionState.STATIONARY,
        ]:
            end_tai = self._end_tai - additional_duration
        if tai >= end_tai:
            if self._commanded_motion_state == LlcMotionState.PARKED:
                motion_state = LlcMotionState.PARKED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state == LlcMotionState.STOPPED:
                motion_state = LlcMotionState.STOPPED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state == LlcMotionState.STATIONARY:
                motion_state = LlcMotionState.STATIONARY
                position = self._end_position
                velocity = 0.0
            else:
                diff_since_crawl_started = tai - end_tai
                calculation_position = self._end_position
                if self._commanded_motion_state == LlcMotionState.CRAWLING:
                    calculation_position = self._start_position
                position = (
                    calculation_position
                    + self._crawl_velocity * diff_since_crawl_started
                )
                motion_state = LlcMotionState.CRAWLING
                velocity = self._crawl_velocity
                if self._crawl_velocity == 0.0:
                    if self._commanded_motion_state in [
                        LlcMotionState.STOPPED,
                        LlcMotionState.MOVING,
                    ]:
                        motion_state = LlcMotionState.STOPPED
                    elif self._commanded_motion_state == LlcMotionState.STATIONARY:
                        motion_state = LlcMotionState.STATIONARY
                    velocity = 0.0
        elif tai < self._start_tai:
            raise ValueError(
                f"Encountered TAI {tai} which is smaller than start TAI {self._start_tai}"
            )
        else:
            if self._current_motion_state in [
                LlcMotionState.MOVING,
                LlcMotionState.CRAWLING,
                LlcMotionState.STOPPED,
            ] and self._commanded_motion_state in [
                LlcMotionState.PARKED,
                LlcMotionState.STATIONARY,
            ]:
                frac_time = (tai - self._start_tai) / (
                    self._end_tai - self._start_tai - additional_duration
                )
            elif self._current_motion_state in [
                LlcMotionState.PARKED,
                LlcMotionState.STATIONARY,
            ] and self._commanded_motion_state in [
                LlcMotionState.MOVING,
                LlcMotionState.CRAWLING,
                LlcMotionState.STOPPED,
            ]:
                frac_time = (tai - self._start_tai - additional_duration) / (
                    self._end_tai - self._start_tai - additional_duration
                )
                self._computed_additional_duration = additional_duration
            elif self._current_motion_state in [
                LlcMotionState.MOVING,
                LlcMotionState.CRAWLING,
            ] and self._commanded_motion_state in [
                LlcMotionState.MOVING,
                LlcMotionState.CRAWLING,
            ]:
                frac_time = (
                    tai - self._start_tai - self._computed_additional_duration
                ) / (
                    self._end_tai - self._start_tai - self._computed_additional_duration
                )
            else:
                frac_time = additional_duration

            position = self._start_position + distance * frac_time
            velocity = self._max_speed
            if distance < 0.0:
                velocity = -self._max_speed
            if self._commanded_motion_state == LlcMotionState.STOPPED:
                motion_state = LlcMotionState.STOPPED
                velocity = 0.0
            elif self._commanded_motion_state == LlcMotionState.STATIONARY:
                motion_state = LlcMotionState.STATIONARY
                velocity = 0.0
            else:
                motion_state = LlcMotionState.MOVING

        position = utils.angle_wrap_nonnegative(math.degrees(position)).rad

        if self.motion_state_in_error:
            velocity = 0.0
            motion_state = LlcMotionState.ERROR

        self._current_motion_state = motion_state
        return position, velocity, motion_state

    def stop(self, start_tai: float) -> float:
        """Stops the current.

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
        position, velocity, motion_state = self.get_position_velocity_and_motion_state(
            tai=start_tai
        )
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = position
        self._crawl_velocity = 0.0
        self._current_motion_state = motion_state
        self._commanded_motion_state = LlcMotionState.STOPPED
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

        Returns
        -------
        `float`
            The expected duration of the command.
        """
        position, velocity, motion_state = self.get_position_velocity_and_motion_state(
            tai=start_tai
        )
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = position
        self._crawl_velocity = 0.0
        self._current_motion_state = motion_state
        self._commanded_motion_state = LlcMotionState.STATIONARY
        self._end_tai = self._start_tai + self._get_duration()
        return self._end_tai - start_tai

    def park(self, start_tai: float) -> float:
        """Parks the dome.

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
        position, velocity, motion_state = self.get_position_velocity_and_motion_state(
            tai=start_tai
        )
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = 0.0
        self._crawl_velocity = 0.0
        self._commanded_motion_state = LlcMotionState.PARKED
        self._current_motion_state = motion_state
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
            self._crawl_velocity = 0.0
            self._current_motion_state = motion_state
            self._commanded_motion_state = LlcMotionState.STATIONARY
            self.motion_state_in_error = False
            self._error_start_tai = 0.0
            self._error_state_position = 0.0
        return 0.0

    def reset_drives_az(self, start_tai: float, reset: list[int]) -> float:
        """Reset one or more AZ drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        reset: array of int
            Desired reset action to execute on each AZ drive: 0 means don't
            reset, 1 means reset.

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

    def calibrate_az(self, start_tai: float) -> float:
        """Take the current position of the dome as zero. This is necessary as
        long as the racks and pinions on the drives have not been installed yet
        to compensate for slippage of the drives.

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
        if self._current_motion_state not in CALIBRATE_AZ_ALLOWED_STATES:
            raise RuntimeError(
                "calibrate_az can only be called when the AMCS in "
                f"{','.join([state.name for state in CALIBRATE_AZ_ALLOWED_STATES])}."
            )
        self._start_position = 0
        self._end_position = 0
        self._start_tai = start_tai
        self._commanded_motion_state = self._current_motion_state
        return 0.0

    def set_fault(self, start_tai: float, drives_in_error: list[int]) -> None:
        """Set the LlcMotionState of AMCS to fault and set the drives in
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

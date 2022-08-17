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

__all__ = ["AzimuthMotion", "NUM_MOTORS"]

import logging
import math

from lsst.ts import utils

from ...enums import IntermediateState, LlcMotionState
from .base_llc_motion_with_crawl import BaseLlcMotionWithCrawl

# The number of motors.
NUM_MOTORS = 5

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
    tuple[LlcMotionState, LlcMotionState],
    list[tuple[IntermediateState, float]],
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


class AzimuthMotion(BaseLlcMotionWithCrawl):
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
        # Keep track of which drives are in error state.
        self.drives_in_error_state = [False] * NUM_MOTORS
        # Keep track of the additional duration needed for the dome to start
        # moving when PARKED or STATIONARY for computations of the position and
        # velocity when MOVING or CRAWLING
        self._computed_additional_duration = 0.0

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

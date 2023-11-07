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

__all__ = ["AzimuthMotion", "NUM_MOTORS"]

import logging
import math

from lsst.ts import utils
from lsst.ts.xml.enums.MTDome import MotionState

from ...enums import InternalMotionState
from .base_llc_motion_with_crawl import BaseLlcMotionWithCrawl

# The number of motors.
NUM_MOTORS = 5

# The mocked duration of an intermediate state.
INTERMEDIATE_STATE_DURATION = 0.5
# The mocked duration for any intermdediate state involving the inflatable
# seal.
INFLATABLE_SEAL_DURATION = 1.0

STATE_SEQUENCE_START_MOTORS = [
    (MotionState.DEFLATING, INFLATABLE_SEAL_DURATION),
    (MotionState.DEFLATED, INFLATABLE_SEAL_DURATION),
    (MotionState.STARTING_MOTOR_COOLING, INTERMEDIATE_STATE_DURATION),
    (MotionState.MOTOR_COOLING_ON, INTERMEDIATE_STATE_DURATION),
    (MotionState.ENABLING_MOTOR_POWER, INTERMEDIATE_STATE_DURATION),
    (MotionState.MOTOR_POWER_ON, INTERMEDIATE_STATE_DURATION),
    (MotionState.GO_NORMAL, INTERMEDIATE_STATE_DURATION),
    (MotionState.DISENGAGING_BRAKES, INTERMEDIATE_STATE_DURATION),
    (MotionState.BRAKES_DISENGAGED, INTERMEDIATE_STATE_DURATION),
]
STATE_SEQUENCE_STOP_MOTORS = [
    (MotionState.ENGAGING_BRAKES, INTERMEDIATE_STATE_DURATION),
    (MotionState.BRAKES_ENGAGED, INTERMEDIATE_STATE_DURATION),
    (MotionState.GO_STATIONARY, INTERMEDIATE_STATE_DURATION),
    (MotionState.DISABLING_MOTOR_POWER, INTERMEDIATE_STATE_DURATION),
    (MotionState.MOTOR_POWER_OFF, INTERMEDIATE_STATE_DURATION),
    (MotionState.STOPPING_MOTOR_COOLING, INTERMEDIATE_STATE_DURATION),
    (MotionState.MOTOR_COOLING_OFF, INTERMEDIATE_STATE_DURATION),
]

# Dict of allowed motion state transitions and the intermediary states between
# those motion states, if applicable.
STATE_TRANSITIONS: dict[
    tuple[MotionState, MotionState],
    list[tuple[MotionState, float]],
] = {
    (MotionState.PARKED, MotionState.MOVING): STATE_SEQUENCE_START_MOTORS,
    (MotionState.PARKED, MotionState.CRAWLING): STATE_SEQUENCE_START_MOTORS,
    (MotionState.MOVING, MotionState.CRAWLING): [],
    (MotionState.CRAWLING, MotionState.MOVING): [],
    (MotionState.CRAWLING, MotionState.STOPPED): [],
    (MotionState.MOVING, MotionState.STOPPED): [],
    (MotionState.MOVING, MotionState.PARKED): STATE_SEQUENCE_STOP_MOTORS,
    (MotionState.CRAWLING, MotionState.PARKED): STATE_SEQUENCE_STOP_MOTORS,
    (MotionState.STOPPED, MotionState.PARKED): STATE_SEQUENCE_STOP_MOTORS,
    (MotionState.MOVING, InternalMotionState.STATIONARY): STATE_SEQUENCE_STOP_MOTORS,
    (MotionState.CRAWLING, InternalMotionState.STATIONARY): STATE_SEQUENCE_STOP_MOTORS,
    (MotionState.STOPPED, InternalMotionState.STATIONARY): STATE_SEQUENCE_STOP_MOTORS,
    (MotionState.STOPPED, MotionState.MOVING): [],
}

CALIBRATE_AZ_ALLOWED_STATES = [
    MotionState.PARKED,
    InternalMotionState.STATIONARY,
    MotionState.STOPPED,
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
        self._commanded_motion_state = MotionState.PARKED
        # Keep track of which drives are in error state.
        self.drives_in_error_state = [False] * NUM_MOTORS
        # Keep track of the additional duration needed for the dome to start
        # moving when PARKED or STATIONARY for computations of the position and
        # velocity when MOVING or CRAWLING
        self._computed_additional_duration = 0.0

    def _get_additional_duration(self) -> float:
        if (
            self._current_motion_state == MotionState.ERROR
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
    ) -> tuple[float, float, MotionState]:
        """Computes the position and `MotionState` for the given TAI time.

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
        motion_state: `MotionState`
            The MotionState at the given TAI time.
        """

        if self.motion_state_in_error:
            tai = self._error_start_tai

        additional_duration = self._get_additional_duration()
        distance = self._get_distance()
        end_tai = self._end_tai
        if self._current_motion_state in [
            MotionState.MOVING,
            MotionState.CRAWLING,
            MotionState.STOPPED,
        ] and self._commanded_motion_state in [
            MotionState.PARKED,
            InternalMotionState.STATIONARY,
        ]:
            end_tai = self._end_tai - additional_duration
        if tai >= end_tai:
            if self._commanded_motion_state == MotionState.PARKED:
                motion_state = MotionState.PARKED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state == MotionState.STOPPED:
                motion_state = MotionState.STOPPED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state == InternalMotionState.STATIONARY:
                motion_state = InternalMotionState.STATIONARY
                position = self._end_position
                velocity = 0.0
            else:
                diff_since_crawl_started = tai - end_tai
                calculation_position = self._end_position
                if self._commanded_motion_state == MotionState.CRAWLING:
                    calculation_position = self._start_position
                position = (
                    calculation_position
                    + self._crawl_velocity * diff_since_crawl_started
                )
                motion_state = MotionState.CRAWLING
                velocity = self._crawl_velocity
                if self._crawl_velocity == 0.0:
                    if self._commanded_motion_state in [
                        MotionState.STOPPED,
                        MotionState.MOVING,
                    ]:
                        motion_state = MotionState.STOPPED
                    elif self._commanded_motion_state == InternalMotionState.STATIONARY:
                        motion_state = InternalMotionState.STATIONARY
                    velocity = 0.0
        elif tai < self._start_tai:
            raise ValueError(
                f"Encountered TAI {tai} which is smaller than start TAI {self._start_tai}"
            )
        elif tai == self._start_tai:
            position = self._start_position
            velocity = self._max_speed
            if distance < 0.0:
                velocity = -self._max_speed
            motion_state = self._current_motion_state
            if self._current_motion_state in [
                MotionState.PARKED,
                MotionState.STOPPED,
                InternalMotionState.STATIONARY,
            ]:
                velocity = 0.0
        else:
            if self._current_motion_state in [
                MotionState.MOVING,
                MotionState.CRAWLING,
                MotionState.STOPPED,
            ] and self._commanded_motion_state in [
                MotionState.PARKED,
                InternalMotionState.STATIONARY,
            ]:
                frac_time = (tai - self._start_tai) / (
                    self._end_tai - self._start_tai - additional_duration
                )
            elif self._current_motion_state in [
                MotionState.PARKED,
                InternalMotionState.STATIONARY,
                MotionState.STOPPED,
            ] and self._commanded_motion_state in [
                MotionState.MOVING,
                MotionState.CRAWLING,
                MotionState.STOPPED,
            ]:
                frac_time = (tai - self._start_tai - additional_duration) / (
                    self._end_tai - self._start_tai - additional_duration
                )
                self._computed_additional_duration = additional_duration
            elif self._current_motion_state in [
                MotionState.MOVING,
                MotionState.CRAWLING,
            ] and self._commanded_motion_state in [
                MotionState.MOVING,
                MotionState.CRAWLING,
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
            if self._commanded_motion_state == MotionState.STOPPED:
                motion_state = MotionState.STOPPED
                velocity = 0.0
            elif self._commanded_motion_state == InternalMotionState.STATIONARY:
                motion_state = InternalMotionState.STATIONARY
                velocity = 0.0
            else:
                motion_state = MotionState.MOVING

        position = utils.angle_wrap_nonnegative(math.degrees(position)).rad

        if self.motion_state_in_error:
            velocity = 0.0
            motion_state = MotionState.ERROR

        self._current_motion_state = motion_state
        return position, velocity, motion_state

    def set_target_position_and_velocity(
        self,
        start_tai: float,
        end_position: float,
        crawl_velocity: float,
        motion_state: MotionState,
    ) -> float:
        """Sets start position and then call the super method.

        Return the duration provided by or raise the exception raised by the
        super method. No aceleration is taken into account.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, at which the command was issued. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        end_position: `float`
            The target position.
        crawl_velocity: `float`
            The crawl_velocity.
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

        curr_position, _, _ = self.get_position_velocity_and_motion_state(tai=start_tai)
        self._start_position = curr_position

        duration = super().set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=end_position,
            crawl_velocity=crawl_velocity,
            motion_state=motion_state,
        )
        self._end_tai = start_tai + duration
        return duration

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
        self._commanded_motion_state = MotionState.PARKED
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

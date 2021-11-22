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
from typing import Tuple

from .base_llc_motion import BaseLlcMotion
from ...enums import LlcMotionState
from lsst.ts import utils


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
    ) -> Tuple[float, float, LlcMotionState]:
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
        if tai >= self._end_tai:
            if self._commanded_motion_state in [
                LlcMotionState.PARKING,
                LlcMotionState.PARKED,
            ]:
                motion_state = LlcMotionState.PARKED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state in [
                LlcMotionState.STOPPING,
                LlcMotionState.STOPPED,
            ]:
                motion_state = LlcMotionState.STOPPED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state in [
                LlcMotionState.GO_STATIONARY,
                LlcMotionState.STATIONARY,
            ]:
                motion_state = LlcMotionState.STATIONARY
                position = self._end_position
                velocity = 0.0
            else:
                diff_since_crawl_started = tai - self._end_tai
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
                        LlcMotionState.STOPPING,
                        LlcMotionState.STOPPED,
                        LlcMotionState.MOVING,
                    ]:
                        motion_state = LlcMotionState.STOPPED
                    elif self._commanded_motion_state in [
                        LlcMotionState.GO_STATIONARY,
                        LlcMotionState.STATIONARY,
                    ]:
                        motion_state = LlcMotionState.STATIONARY
                    velocity = 0.0
        elif tai < self._start_tai:
            raise ValueError(
                f"Encountered TAI {tai} which is smaller than start TAI {self._start_tai}"
            )
        else:
            frac_time = (tai - self._start_tai) / (self._end_tai - self._start_tai)
            distance = self._get_distance()
            position = self._start_position + distance * frac_time
            velocity = self._max_speed
            if distance < 0.0:
                velocity = -self._max_speed
            if self._commanded_motion_state == LlcMotionState.PARKING:
                motion_state = LlcMotionState.PARKING
            elif self._commanded_motion_state == LlcMotionState.STOPPING:
                motion_state = LlcMotionState.STOPPED
                velocity = 0.0
            elif self._commanded_motion_state == LlcMotionState.GO_STATIONARY:
                motion_state = LlcMotionState.STATIONARY
                velocity = 0.0
            else:
                motion_state = LlcMotionState.MOVING

        position = utils.angle_wrap_nonnegative(math.degrees(position)).rad
        return position, velocity, motion_state

    def stop(self, start_tai: float) -> None:
        """Stops the current.

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
        self._crawl_velocity = 0.0
        self._commanded_motion_state = LlcMotionState.STOPPING

    def go_stationary(self, start_tai: float) -> None:
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
        self._crawl_velocity = 0.0
        self._commanded_motion_state = LlcMotionState.GO_STATIONARY

    def park(self, start_tai: float) -> float:
        """Parks the dome.

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
        self._end_position = 0.0
        self._crawl_velocity = 0.0
        self._commanded_motion_state = LlcMotionState.PARKING
        self._end_tai = self._start_tai + self._get_duration()
        return self._end_tai

    def exit_fault(self, start_tai: float) -> None:
        """Clear the fault state.

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
        self._crawl_velocity = 0.0
        self._commanded_motion_state = LlcMotionState.GO_STATIONARY

# This file is part of ts_Dome.
#
# Developed for the LSST Data Management System.
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

__all__ = ["ElevationMotion"]

import logging
import math

from lsst.ts.idl.enums.Dome import MotionState


class ElevationMotion:
    """Simulator for the elevation motion of the light and wind screen of the
    Dome.

    Parameters
    ----------
    start_position: `float`
        The initial position.
    min_position: `float`
        The minimum allowed position.
    max_position: `float`
        The maximum allowed position.
    max_speed: `float`
        The maximum allowed speed. If the provided abs(velocity) is lower then
        `MotionState` CRAWLING is assumed, MOVING otherwise.
    start_tai: `float`
        The current TAI time.

    Notes
    -----
    This simulator can either move the light and wind screen to a target
    position at maximum speed and stop, or crawl at the specified velocity. It
    handles the 0 and 1/2pi radians (0 and 90 degrees) boundaries by stopping
    there. When either moving or crawling, a new move or crawl command is
    handled and the elevation motion/crawl can be stopped. To "park" the light
    and wind screen, it needs to be moved to position 0.

    """

    def __init__(
        self, start_position, min_position, max_position, max_speed, start_tai
    ):
        self._start_position = start_position
        self._min_position = min_position
        self._max_position = max_position
        self._max_speed = max_speed
        self._motion_state = MotionState.STOPPED
        self._start_tai = start_tai
        self._target_position = 0
        self._velocity = 0
        self.log = logging.getLogger("MockPointToPointActuator")

    @property
    def start_position(self):
        return self._start_position

    def set_target_position_and_velocity(self, start_tai, target_position, velocity):
        """Sets the end_position and velocity and returns the duration of
        the move.

        No aceleration is taken into account.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position.
        velocity: `float`
            The velocity.

        Returns
        -------
        duration: `float`
            The duration of the move.

        Raises
        ------
        ValueError
            If the target position falls outside the range
            [min position, max position] or if abs(velocity) > max_speed.

        """
        if not self._min_position <= target_position <= self._max_position:
            raise ValueError(
                f"The target position {target_position} is outside of the "
                f"range [{self._min_position, self._max_position}]"
            )
        if math.fabs(velocity) > self._max_speed:
            raise ValueError(
                f"The target speed {math.fabs(velocity)} is larger than the "
                f"max speed {self._max_speed}."
            )
        position, motion_state = self.get_position_and_motion_state(tai=start_tai)
        self._start_position = position
        self._start_tai = start_tai
        self._target_position = target_position
        self._velocity = velocity
        duration = (self._target_position - self._start_position) / self._velocity
        return duration

    def get_position_and_motion_state(self, tai):
        """Computes the position and `MotionState` for the given TAI time.

        Parameters
        ----------
        tai: `float`
            The TAI time for which to compute the position.

        Returns
        -------
        position: `float`
            The position at the given TAI time.
        """
        position = self._start_position + self._velocity * (tai - self._start_tai)
        self._motion_state = MotionState.MOVING
        if self._velocity == 0:
            self._motion_state = MotionState.STOPPED
        elif math.fabs(self._velocity) < self._max_speed:
            self._motion_state = MotionState.CRAWLING

        if self._motion_state == MotionState.CRAWLING:
            if position >= self._max_position:
                position = self._max_position
                self._start_position = self._max_position
                self._velocity = 0
                self._motion_state = MotionState.STOPPED
            elif position <= self._min_position:
                position = self._min_position
                self._start_position = self._min_position
                self._velocity = 0
                self._motion_state = MotionState.STOPPED
        elif self._motion_state == MotionState.MOVING:
            if position >= self._target_position and self._velocity > 0:
                position = self._target_position
                self._velocity = 0
                self._motion_state = MotionState.STOPPED
            elif position <= self._target_position and self._velocity < 0:
                position = self._target_position
                self._velocity = 0
                self._motion_state = MotionState.STOPPED
        return position, self._motion_state

    def stop(self, start_tai):
        """Stops the current motion instantaneously.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        """
        position, motion_state = self.get_position_and_motion_state(tai=start_tai)
        self._start_position = position
        self._target_position = position
        self._velocity = 0

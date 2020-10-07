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

__all__ = ["AzimuthMotion"]

import logging
import math

from lsst.ts.idl.enums.Dome import MotionState


class AzimuthMotion:
    """Simulator for the azimuth motion of the Dome.

    Parameters
    ----------
    initial_position: `float`
        The initial position [rad].
    max_speed: `float`
        The maximum allowed speed [rad/s].
    current_tai: `float`
        The current TAI time.

    Notes
    -----
    This simulator can either move the dome to a target position at maximum
    speed and start crawling from there with the specified crawl velocity, or
    crawl at the specified velocity. It handles the 0/2pi radians (0/360
    degrees) boundary. When either moving or crawling, a new move or handle
    command is handled, the azimuth motion/crawl can be stopped and the dome
    can be parked.
    """

    def __init__(self, initial_position, max_speed, current_tai):
        self._initial_position = initial_position
        self._motion_state = MotionState.STOPPED
        self._commanded_tai = current_tai
        self._target_position = 0
        self._max_speed = max_speed
        self._move_velocity = 0
        self._crawl_velocity = 0
        self._do_move = True
        self.log = logging.getLogger("MockCircularCrawlingActuator")

    def determine_distance_and_move_speed(self):
        """Determines the smallest distance [rad] between the initial and
        target positions assuming motion around a circle. The move velocity is
        determined at the same time as well.

        Returns
        -------
        distance: `float`
            The smallest distance between the initial and target positions.

        """
        distance = self._target_position - self._initial_position
        self._move_velocity = self._max_speed
        if distance >= math.pi:
            distance -= 2 * math.pi
            self._move_velocity = -self._max_speed
        elif distance > 0:
            self._move_velocity = self._max_speed
        elif distance < -math.pi:
            distance += 2 * math.pi
            self._move_velocity = self._max_speed
        elif distance < 0:
            self._move_velocity = -self._max_speed
        return distance

    def get_duration(self, distance):
        duration = math.fabs(distance / self._move_velocity)
        if not self._do_move:
            duration = 0
        return duration

    def set_target_position_and_velocity(
        self, commanded_tai, target_position, crawl_velocity, do_move
    ):
        """Sets the target_position and crawl velocity and returns the duration
        of the move.

        No aceleration is taken into account. The time taken by crawling is not
        taken into account either.

        Parameters
        ----------
        commanded_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position [rad]. Ignored if `do_move` is False.
        crawl_velocity: `float`
            The velocity [rad/s] at which to crawl once the move is done.
        do_move: `bool`
            Move and then crawl (True) or crawl only (False).

        Returns
        -------
        duration: `float`
            The duration [s] of the move.

        Raises
        ------
        ValueError
            If abs(crawl_velocity) > max_speed.

        """
        if math.fabs(crawl_velocity) > self._max_speed:
            raise ValueError(
                f"The target crawl speed {math.fabs(crawl_velocity)} is larger"
                f" than the max speed {self._max_speed}."
            )

        position, motion_state = self.get_position_and_motion_state(tai=commanded_tai)
        self._initial_position = position
        self._commanded_tai = commanded_tai
        self._target_position = target_position
        self._crawl_velocity = crawl_velocity
        self._do_move = do_move
        distance = self.determine_distance_and_move_speed()
        duration = self.get_duration(distance)
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
            The position [rad] at the given TAI time, taking both the move
            (optional)) and crawl velocities into account.
        """
        distance = self.determine_distance_and_move_speed()
        duration = self.get_duration(distance)
        if not self._do_move and self._motion_state not in [
            MotionState.PARKING,
            MotionState.STOPPING,
        ]:
            position = self._initial_position + self._crawl_velocity * (
                tai - self._commanded_tai
            )
            self._motion_state = MotionState.CRAWLING
            if self._crawl_velocity == 0:
                self._motion_state = MotionState.STOPPED
        elif tai - self._commanded_tai >= duration:
            if self._motion_state in [MotionState.PARKING, MotionState.PARKED]:
                self._motion_state = MotionState.PARKED
                position = self._target_position
                self._move_velocity = 0
                self._crawl_velocity = 0
            elif self._motion_state in [MotionState.STOPPING, MotionState.STOPPED]:
                self._motion_state = MotionState.STOPPED
                position = self._target_position
                self._move_velocity = 0
                self._crawl_velocity = 0
            else:
                diff_since_crawl_started = tai - self._commanded_tai - duration
                position = (
                    self._target_position
                    + self._crawl_velocity * diff_since_crawl_started
                )
                self._motion_state = MotionState.CRAWLING
                if self._crawl_velocity == 0:
                    self._motion_state = MotionState.STOPPED
        else:
            position = self._initial_position + self._move_velocity * (
                tai - self._commanded_tai
            )
            if self._motion_state not in [
                MotionState.PARKING,
                MotionState.STOPPING,
            ]:
                self._motion_state = MotionState.MOVING

        if position >= 2 * math.pi:
            position -= 2 * math.pi
        elif position < 0:
            position += 2 * math.pi
        return position, self._motion_state

    def stop(self, commanded_tai):
        """Stops the current motion instantaneously.

        Parameters
        ----------
        commanded_tai: `float`
            The TAI time at which the command was issued.
        """
        position, motion_state = self.get_position_and_motion_state(tai=commanded_tai)
        self._commanded_tai = commanded_tai
        self._initial_position = position
        self._target_position = position
        self._move_velocity = 0
        self._crawl_velocity = 0
        self._motion_state = MotionState.STOPPING

    def park(self, commanded_tai):
        """Parks the dome.

        Parameters
        ----------
        commanded_tai: `float`
            The TAI time at which the command was issued.
        """
        position, motion_state = self.get_position_and_motion_state(tai=commanded_tai)
        self._commanded_tai = commanded_tai
        self._initial_position = position
        self._target_position = 0
        self.determine_distance_and_move_speed()
        self._crawl_velocity = 0
        self._motion_state = MotionState.PARKING
        self._do_move = True

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
import lsst.ts.salobj as salobj


class AzimuthMotion:
    """Simulator for the azimuth motion of the Dome.

    Parameters
    ----------
    start_position: `float`
        The start position [rad] of the move.
    max_speed: `float`
        The maximum allowed speed [rad/s].
    start_tai: `float`
        The TAI time of the start of the move. This also needs to be set in the
        constructor so this class knows what the TAI time currently is.

    Notes
    -----
    This simulator can either move the dome to a target position at maximum
    speed and start crawling from there with the specified crawl velocity, or
    crawl at the specified velocity. It handles the 0/2pi radians boundary.
    When either moving or crawling, a new move or handle command is handled,
    the azimuth motion/crawl can be stopped and the dome can be parked.
    """

    def __init__(self, start_position, max_speed, start_tai):
        # This defines the start position of a move or a crawl.
        self._start_position = start_position
        # The commanded MotionState, against which the computed MotionState
        # will be compared. By default the azimuth motion starts in STOPPED
        # state. The MotionState only changes when a new command is received.
        self._commanded_motion_state = MotionState.STOPPED
        # This defines the end position of the move, after which crawling will
        # start in case of a move command. Ignored in case of a crawl command.
        # In case of a park command, the end position will always be 0 and no
        # crawling will follow.
        self._end_position = 0
        # This defines the TAI time at which a move or crawl will start.
        self._start_tai = start_tai
        # This defines the TAI time at which the move will end, after which
        # crawling will start in case of a move command. Ignored in case of a
        # crawl command. Also used in case of a park command but no crawl will
        # follow.
        self._end_tai = 0
        # This is not a constant but can be configured by the Dome CSC, which
        # is why it is a parameter.
        self._max_speed = max_speed
        # When a move or park command is received, the move velocity is
        # determined as the move speed in the correct direction.
        self._move_velocity = 0
        # When a move or crawl command is received, it specifies the crawl
        # velocity.
        self._crawl_velocity = 0
        # The computed motion state
        self._motion_state = None

        self.log = logging.getLogger("MockCircularCrawlingActuator")

    def determine_distance_and_move_velocity(self):
        """Determines the smallest distance [rad] between the initial and
        target positions assuming motion around a circle. The move velocity is
        determined at the same time as well.

        Returns
        -------
        distance: `float`
            The smallest distance between the initial and target positions.
        move_velocity: `float`
            The velocity at which the move will be performed.

        """
        distance = salobj.angle_diff(
            math.degrees(self._end_position), math.degrees(self._start_position)
        ).rad
        move_velocity = self._max_speed if distance >= 0 else -self._max_speed
        return distance, move_velocity

    def get_duration(self, distance):
        duration = math.fabs(distance / self._move_velocity)
        if self._commanded_motion_state == MotionState.CRAWLING:
            # A crawl command is executed instantaneously.
            duration = 0
        return duration

    def set_target_position_and_velocity(
        self, start_tai, end_position, crawl_velocity, motion_state
    ):
        """Sets the target_position and crawl velocity and returns the duration
        of the move.

        No aceleration is taken into account. The time taken by crawling is not
        taken into account either.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        end_position: `float`
            The end position [rad] of the move. Ignored if `do_move` is False.
        crawl_velocity: `float`
            The velocity [rad/s] at which to crawl once the move is done.
        motion_state: `MotionState`
            MOVING or CRAWLING. The value is not checked.

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

        self._commanded_motion_state = motion_state
        self._start_tai = start_tai
        self._end_position = end_position
        self._crawl_velocity = crawl_velocity
        distance, self._move_velocity = self.determine_distance_and_move_velocity()
        duration = self.get_duration(distance)
        self._end_tai = self._start_tai + duration
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
        if tai >= self._end_tai:
            if self._commanded_motion_state in [
                MotionState.PARKING,
                MotionState.PARKED,
            ]:
                self._motion_state = MotionState.PARKED
                position = self._end_position
                self._move_velocity = 0
                self._crawl_velocity = 0
            elif self._commanded_motion_state in [
                MotionState.STOPPING,
                MotionState.STOPPED,
            ]:
                self._motion_state = MotionState.STOPPED
                position = self._end_position
                self._move_velocity = 0
                self._crawl_velocity = 0
            else:
                diff_since_crawl_started = tai - self._end_tai
                calculation_position = self._end_position
                if self._commanded_motion_state == MotionState.CRAWLING:
                    calculation_position = self._start_position
                position = (
                    calculation_position
                    + self._crawl_velocity * diff_since_crawl_started
                )
                self._motion_state = MotionState.CRAWLING
                if self._crawl_velocity == 0:
                    self._motion_state = MotionState.STOPPED
        elif tai < self._start_tai:
            raise ValueError(
                f"Encountered TAI {tai} which is smaller than start TAI {self._start_tai}"
            )
        else:
            position = self._start_position + self._move_velocity * (
                tai - self._start_tai
            )
            if self._commanded_motion_state == MotionState.PARKING:
                self._motion_state = MotionState.PARKING
            elif self._commanded_motion_state == MotionState.STOPPING:
                self._motion_state = MotionState.STOPPED
            else:
                self._motion_state = MotionState.MOVING

        position = salobj.angle_wrap_nonnegative(math.degrees(position)).rad
        return position, self._motion_state

    def stop(self, start_tai):
        """Stops the current motion instantaneously.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        """
        position, motion_state = self.get_position_and_motion_state(tai=start_tai)
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = position
        self._move_velocity = 0
        self._crawl_velocity = 0
        self._commanded_motion_state = MotionState.STOPPING

    def park(self, start_tai):
        """Parks the dome.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        """
        position, motion_state = self.get_position_and_motion_state(tai=start_tai)
        self._start_tai = start_tai
        self._start_position = position
        self._end_position = 0
        self._crawl_velocity = 0
        self._commanded_motion_state = MotionState.PARKING
        distance, self._move_velocity = self.determine_distance_and_move_velocity()
        self._end_tai = self._start_tai + self.get_duration(distance)
        return self._end_tai

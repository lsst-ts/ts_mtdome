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
from typing import Tuple

from abc import ABC, abstractmethod

from ...enums import LlcMotionState
from lsst.ts import utils


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
        self._end_position = 0.0
        # This defines the minimum allowed position.
        self._min_position = min_position
        # This defines the maximum allowed position.
        self._max_position = max_position
        # This is not a constant but can be configured by the MTDome CSC, which
        # is why it is a parameter.
        self._max_speed = max_speed
        # The commanded LlcMotionState, against which the computed
        # LlcMotionState will be compared. By default the elevation motion
        # starts in STOPPED state. The LlcMotionState only changes when a new
        # command is received.
        self._commanded_motion_state = LlcMotionState.STOPPED
        # This defines the TAI time, unix seconds, at which a move or crawl
        # will start. To model the real dome, this should be the current time.
        # However, for unit tests it can be convenient to use other values.
        self._start_tai = start_tai
        # This defines the TAI time, unix seconds, at which the move will end,
        # after which all motion is stopped. Ignored in case of a crawl
        # command. To model the real dome, this should be the current time.
        # However, for unit tests it can be convenient to use other values.
        self._end_tai = 0.0
        # When a move or crawl command is received, it specifies the crawl
        # crawl_velocity.
        self._crawl_velocity = 0.0

    def _get_distance(self) -> float:
        """Determines the smallest distance [rad] between the initial and
        target positions assuming motion around a circle.

        Returns
        -------
        distance: `float`
            The smallest distance between the initial and target positions.
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
        if self._commanded_motion_state == LlcMotionState.CRAWLING:
            # A crawl command is executed instantaneously.
            duration = 0
        return duration

    def set_target_position_and_velocity(
        self,
        start_tai: float,
        end_position: float,
        crawl_velocity: float,
        motion_state: LlcMotionState,
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
        crawl_velocity: `float`
            The crawl_velocity.
        motion_state: `LlcMotionState`
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
        if not self._min_position <= end_position <= self._max_position:
            raise ValueError(
                f"The target position {end_position} is outside of the "
                f"range [{self._min_position, self._max_position}]"
            )
        if math.fabs(crawl_velocity) > self._max_speed:
            raise ValueError(
                f"The target speed {math.fabs(crawl_velocity)} is larger than the "
                f"max speed {self._max_speed}."
            )

        self._commanded_motion_state = motion_state
        self._start_tai = start_tai
        self._end_position = end_position
        self._crawl_velocity = crawl_velocity
        duration = self._get_duration()
        self._end_tai = self._start_tai + duration
        return duration

    @abstractmethod
    def get_position_velocity_and_motion_state(
        self, tai: float
    ) -> Tuple[float, float, LlcMotionState]:
        pass

    @abstractmethod
    def stop(self, start_tai: float) -> None:
        pass

    @abstractmethod
    def park(self, start_tai: float) -> float:
        pass

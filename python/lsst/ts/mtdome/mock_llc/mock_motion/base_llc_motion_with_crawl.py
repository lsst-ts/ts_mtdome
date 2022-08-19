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

from ...enums import LlcMotionState
from .base_llc_motion import BaseLlcMotion


class BaseLlcMotionWithCrawl(BaseLlcMotion):
    def __init__(
        self,
        start_position: float,
        min_position: float,
        max_position: float,
        max_speed: float,
        start_tai: float,
    ):
        super().__init__(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )

        # When a move or crawl command is received, it specifies the crawl
        # crawl_velocity.
        self._crawl_velocity = 0.0

    def _get_duration(self) -> float:
        """Determines the duration of the move using the distance of the move
        and the maximum speed, or zero in case of a crawl.

        Returns
        -------
        duration: `float`
            The duration of the move, or zero in case of a crawl.
        """
        # Call the super method first because it calls the default case which
        # is for MOVING.
        duration = super()._get_duration()
        # Next check if CRAWLING.
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
        if math.fabs(crawl_velocity) > self._max_speed:
            raise ValueError(
                f"The target speed {math.fabs(crawl_velocity)} is larger than the "
                f"max speed {self._max_speed}."
            )

        self._crawl_velocity = crawl_velocity
        duration = self.base_set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=end_position,
            motion_state=motion_state,
        )
        return duration

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
        if self.motion_state_in_error:
            self._crawl_velocity = 0.0
            super().exit_fault(start_tai=start_tai)
        return 0.0

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

__all__ = [
    "ShutterMotion",
    "CLOSED_POSITION",
    "NUM_MOTORS_PER_SHUTTER",
    "OPEN_POSITION",
    "SHUTTER_SPEED",
]

import logging
import math

from lsst.ts.xml.enums.MTDome import MotionState

from ...enums import InternalMotionState
from .base_llc_motion_without_crawl import BaseLlcMotionWithoutCrawl

# The number of motors per shutter.
NUM_MOTORS_PER_SHUTTER = 2

# The shutter is 0% open.
CLOSED_POSITION = 0.0
# The shutter is 100% open.
OPEN_POSITION = 100.0
# The shutter speed (%/s). This is an assumed value such that the shutter opens
# or closes in 10 seconds.
SHUTTER_SPEED = 10.0


class ShutterMotion(BaseLlcMotionWithoutCrawl):
    """Simulator for one door (of two) of the aperture shutter motion of the
    MTDome.

    Parameters
    ----------
    start_position: `float`
        The initial position [%].
    start_tai: `float`
        The current TAI time, unix seconds. To model the real dome, this should
        be the current time. However, for unit tests it can be convenient to
        use other values.
    """

    def __init__(
        self,
        start_position: float,
        start_tai: float,
    ):
        super().__init__(
            start_position=start_position,
            min_position=CLOSED_POSITION,
            max_position=OPEN_POSITION,
            max_speed=SHUTTER_SPEED,
            start_tai=start_tai,
        )
        self.log = logging.getLogger("ShutterMotion")
        # Keep track of which drives are in error state.
        self.drives_in_error_state = [False] * NUM_MOTORS_PER_SHUTTER

    def _get_duration(self) -> float:
        # This override is needed because the shutter doesn't use angles (in
        # radians) but percentages.
        duration = math.fabs(
            (self._end_position - self._start_position) / SHUTTER_SPEED
        )
        return duration

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
            The position [%] at the given TAI time, taking the move velocity
            into account.
        velocity: `float`
            The velocity [%/s] at the given TAI time.
        motion_state: `MotionState`
            The MotionState of the shutter door at the given TAI time.
        """

        if self.motion_state_in_error:
            tai = self._error_start_tai

        if tai >= self._end_tai:
            if self._commanded_motion_state in [
                MotionState.STOPPED,
                MotionState.MOVING,
            ]:
                motion_state = MotionState.STOPPED
                position = self._end_position
                velocity = 0.0
            elif self._commanded_motion_state == InternalMotionState.STATIONARY:
                motion_state = InternalMotionState.STATIONARY
                position = self._end_position
                velocity = 0.0
            else:
                raise ValueError(
                    f"Encountered unexpected commanded motion state={self._commanded_motion_state}"
                )
        elif tai < self._start_tai:
            raise ValueError(
                f"Encountered TAI {tai} which is smaller than start TAI {self._start_tai}"
            )
        else:
            frac_time = (tai - self._start_tai) / (self._end_tai - self._start_tai)
            distance = self._end_position - self._start_position
            position = self._start_position + distance * frac_time
            velocity = SHUTTER_SPEED
            if distance < 0.0:
                velocity = -SHUTTER_SPEED
            if self._commanded_motion_state == MotionState.STOPPED:
                motion_state = MotionState.STOPPED
                velocity = 0.0
            elif self._commanded_motion_state == InternalMotionState.STATIONARY:
                motion_state = InternalMotionState.STATIONARY
                velocity = 0.0
            else:
                motion_state = MotionState.MOVING

        if self.motion_state_in_error:
            velocity = 0.0
            motion_state = MotionState.ERROR

        return position, velocity, motion_state

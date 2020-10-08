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

__all__ = ["LwscsStatus"]

import logging
import math

import numpy as np

from .base_mock_status import BaseMockStatus
from ..llc_configuration_limits.lwscs_limits import LwscsLimits
from lsst.ts.idl.enums.Dome import MotionState
from .mock_motion.elevation_motion import ElevationMotion

_NUM_MOTORS = 2


class LwscsStatus(BaseMockStatus):
    """Represents the status of the Light and Wind Screen Control System in
    simulation mode.

    Parameters
    ----------
    start_tai: `float`
        The current TAI time.
    """

    def __init__(self, start_tai):
        super().__init__()
        self.log = logging.getLogger("MockLwscsStatus")
        self.lwscs_limits = LwscsLimits()
        # default values which may be overriden by calling moveEl, crawlEl or
        # config
        self.jmax = self.lwscs_limits.jmax
        self.amax = self.lwscs_limits.amax
        self.vmax = self.lwscs_limits.vmax
        # variables helping with the state of the mock EL motion
        self.elevation_motion = ElevationMotion(
            start_position=0,
            min_position=0,
            max_position=math.pi,
            max_speed=math.fabs(self.vmax),
            start_tai=start_tai,
        )
        self.duration = 0.0
        # variables holding the status of the mock EL motion
        self.status = MotionState.STOPPED
        self.position_commanded = 0
        self.velocity_actual = 0
        self.velocity_commanded = 0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.power_draw = 0.0

    async def determine_status(self, start_tai):
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        position, motion_state = self.elevation_motion.get_position_and_motion_state(
            tai=start_tai
        )
        self.llc_status = {
            "status": motion_state,
            "positionActual": position,
            "positionCommanded": self.position_commanded,
            "velocityActual": self.velocity_actual,
            "velocityCommanded": self.velocity_commanded,
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTemperature": self.drive_temperature.tolist(),
            "encoderHeadRaw": self.encoder_head_raw.tolist(),
            "encoderHeadCalibrated": self.encoder_head_calibrated.tolist(),
            "resolverRaw": self.resolver_raw.tolist(),
            "resolverCalibrated": self.resolver_calibrated.tolist(),
            "powerDraw": self.power_draw,
            "timestampUTC": start_tai,
        }
        self.log.debug(f"lwscs_state = {self.llc_status}")

    async def moveEl(self, position, start_tai):
        """Move the light and wind screen to the given elevation.

        Parameters
        ----------
        position: `float`
            The position (rad) to move to. 0 means point to the horizon and
            pi/2 point to the zenith. These limits are not checked.
        start_tai: `float`
            The current TAI time
        """
        self.position_commanded = position
        motion_velocity = self.vmax
        if self.position_commanded < self.elevation_motion.start_position:
            motion_velocity = -self.vmax
        self.duration = self.elevation_motion.set_target_position_and_velocity(
            start_tai=start_tai, target_position=position, velocity=motion_velocity,
        )
        return self.duration

    async def crawlEl(self, velocity, start_tai):
        """Crawl the light and wind screen in the given direction at the given
        velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked
            against the velocity limits for the light and wind screen.
        start_tai: `float`
            The current TAI time
        """
        self.position_commanded = math.pi
        if velocity < 0:
            self.position_commanded = 0
        self.duration = self.elevation_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            target_position=self.position_commanded,
            velocity=velocity,
        )
        return self.duration

    async def stopEl(self, start_tai):
        """Stop moving the light and wind screen.

        Parameters
        ----------
        start_tai: `float`
            The current TAI time

        """
        self.elevation_motion.stop(start_tai)
        self.duration = 0.0
        return self.duration

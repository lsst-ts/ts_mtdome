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

__all__ = ["LwscsStatus", "CURRENT_PER_MOTOR", "NUM_MOTORS"]

import logging
import math

import numpy as np
from lsst.ts.xml.enums.MTDome import MotionState

from ..llc_configuration_limits.lwscs_limits import LwscsLimits
from ..power_management.power_draw_constants import LWS_POWER_DRAW
from .base_mock_llc import DOME_VOLTAGE, BaseMockStatus
from .mock_motion.elevation_motion import ElevationMotion

NUM_MOTORS = 2

# Current drawn per motor by the Light Wind Screen [A].
CURRENT_PER_MOTOR = LWS_POWER_DRAW / NUM_MOTORS / DOME_VOLTAGE


class LwscsStatus(BaseMockStatus):
    """Represents the status of the Light and Wind Screen Control System in
    simulation mode.

    Parameters
    ----------
    start_tai: `float`
        The TAI time, unix seconds, at the time at which this class is
        instantiated.  To model the real dome, this should be the current time.
        However, for unit tests it can be convenient to use other values.
    """

    def __init__(self, start_tai: float) -> None:
        super().__init__()
        self.log = logging.getLogger("MockLwscsStatus")
        self.lwscs_limits = LwscsLimits()

        # Default values which may be overriden by calling moveEl, crawlEl or
        # config
        self.jmax = self.lwscs_limits.jmax
        self.amax = self.lwscs_limits.amax
        self.vmax = self.lwscs_limits.vmax

        # Variables helping with the state of the mock EL motion
        self.elevation_motion = ElevationMotion(
            start_position=0.0,
            min_position=0.0,
            max_position=math.pi,
            max_speed=math.fabs(self.vmax),
            start_tai=start_tai,
        )

        # Keep the end TAI time as a reference for unit tests
        self.end_tai = 0.0

        # Variables holding the status of the mock EL motion
        self.status = MotionState.STOPPED
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.position_commanded = 0.0
        self.velocity_commanded = 0.0
        self.drive_torque_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(NUM_MOTORS, dtype=float)
        self.resolver_raw = np.zeros(NUM_MOTORS, dtype=float)
        self.resolver_calibrated = np.zeros(NUM_MOTORS, dtype=float)
        self.power_draw = 0.0

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.

        Parameters
        ----------
        current_tai: `float`
            The TAI time, unix seconds, for which the status is requested. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        """
        (
            position,
            velocity,
            motion_state,
        ) = self.elevation_motion.get_position_velocity_and_motion_state(
            tai=current_tai
        )
        # Determine the current drawn by the light wind screen motors. Here
        # fixed current values are assumed while in reality they vary depending
        # on the speed and the inclination of the light wind screen.
        if motion_state in [MotionState.CRAWLING, MotionState.MOVING]:
            self.drive_current_actual = np.full(
                NUM_MOTORS, CURRENT_PER_MOTOR, dtype=float
            )
            self.power_draw = LWS_POWER_DRAW
        else:
            self.drive_current_actual = np.zeros(NUM_MOTORS, dtype=float)
            self.power_draw = 0.0
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": motion_state.name,
                "operationalMode": self.operational_mode.name,
            },
            "positionActual": position,
            "positionCommanded": self.position_commanded,
            "velocityActual": velocity,
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
            "appliedConfiguration": {
                "jmax": self.jmax,
                "amax": self.amax,
                "vmax": self.vmax,
            },
            "timestampUTC": current_tai,
        }
        self.log.debug(f"lwscs_state = {self.llc_status}")

    async def moveEl(self, position: float, start_tai: float) -> float:
        """Move the light and wind screen to the given elevation.

        Parameters
        ----------
        position: `float`
            The position (rad) to move to. 0 means point to the horizon and
            pi/2 point to the zenith. These limits are not checked.
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        self.position_commanded = position
        duration = self.elevation_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=position,
            crawl_velocity=0,
            motion_state=MotionState.MOVING,
        )
        self.end_tai = start_tai + duration
        return duration

    async def crawlEl(self, velocity: float, start_tai: float) -> float:
        """Crawl the light and wind screen in the given direction at the given
        velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked
            against the velocity limits for the light and wind screen.
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        # If the velocity is positive then crawl toward the highest possible
        # elevation, otherwise to the lowest.
        self.position_commanded = math.pi / 2.0
        if velocity < 0:
            self.position_commanded = 0

        duration = self.elevation_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=self.position_commanded,
            crawl_velocity=velocity,
            motion_state=MotionState.CRAWLING,
        )
        self.end_tai = start_tai + duration
        return duration

    async def stopEl(self, start_tai: float) -> float:
        """Stop moving the light and wind screen.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        """
        duration = self.elevation_motion.stop(start_tai)
        self.end_tai = start_tai + duration
        return duration

    async def go_stationary(self, start_tai: float) -> float:
        """Stop elevation motion and engage the brakes. Also disengage the
        locking pins if engaged.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        """
        duration = self.elevation_motion.go_stationary(start_tai)
        self.end_tai = start_tai + duration
        return duration

    async def exit_fault(self, start_tai: float) -> float:
        """Clear the fault state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        self.elevation_motion.exit_fault(start_tai)
        duration = 0.0
        self.end_tai = start_tai
        return duration

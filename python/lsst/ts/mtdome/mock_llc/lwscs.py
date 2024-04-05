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
from lsst.ts import utils
from lsst.ts.xml.enums.MTDome import MotionState

from ..enums import InternalMotionState
from ..llc_configuration_limits.lwscs_limits import LwscsLimits
from ..power_management.power_draw_constants import LWS_POWER_DRAW
from .base_mock_llc import DOME_VOLTAGE, BaseMockStatus

NUM_MOTORS = 2

MIN_POSITION = 0.0
MAX_POSITION = math.pi / 2.0

# Current drawn per motor by the Light Wind Screen [A].
CURRENT_PER_MOTOR = LWS_POWER_DRAW / NUM_MOTORS / DOME_VOLTAGE


def get_distance(start_position: float, end_position: float) -> float:
    """Determines the smallest distance [rad] between the initial and
    target positions assuming motion around a circle.

    Parameters
    ----------
    start_position : `float`
        The start position [rad].
    end_position : `float`
        The end position [rad].

    Returns
    -------
    distance: `float`
        The smallest distance [rad] between the initial and target positions.
    """
    distance = utils.angle_diff(
        math.degrees(end_position), math.degrees(start_position)
    ).rad
    return distance


def get_duration(start_position: float, end_position: float, max_speed: float) -> float:
    """Determines the duration of the move using the distance of the move
    and the maximum speed, or zero in case of a crawl.

    Parameters
    ----------
    start_position : `float`
        The start position.
    end_position : `float`
        The end position.
    max_speed : `float`
        The maximum speed.

    Returns
    -------
    duration : `float`
        The duration of the move, or zero in case of a crawl.
    """
    duration = math.fabs(get_distance(start_position, end_position)) / max_speed
    return duration


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
        self.start_position = 0.0
        self.crawl_velocity = 0.0
        self.start_tai = 0.0
        self.end_tai = 0.0

        # Variables holding the status of the mock EL motion
        self.status = MotionState.STOPPED
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.position_actual = 0.0
        self.position_commanded = 0.0
        self.velocity_actual = 0.0
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

        # State machine related attributes.
        self.current_state = MotionState.PARKED.name
        self.target_state = MotionState.PARKED.name

    async def evaluate_state(self, current_tai: float) -> None:
        """Evaluate the state and perform a state transition if necessary.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        # No state machine yet.
        await self._handle_motion(current_tai)

    async def _handle_motion(self, current_tai: float) -> None:
        # No state machine yet.
        await self._handle_moving_or_crawling(current_tai)

    async def _handle_moving_or_crawling(self, current_tai: float) -> None:
        distance = get_distance(self.start_position, self.position_commanded)
        if current_tai >= self.end_tai:
            await self._handle_past_end_tai(current_tai)
        elif current_tai < self.start_tai:
            raise ValueError(
                f"Encountered TAI {current_tai} which is smaller than start TAI {self.start_tai}."
            )
        else:
            frac_time = (current_tai - self.start_tai) / (self.end_tai - self.start_tai)
            self.position_actual = self.start_position + distance * frac_time
            self.velocity_actual = self.vmax
            if distance < 0.0:
                self.velocity_actual = -self.vmax
            if self.target_state == MotionState.STOPPED.name:
                self.current_state = MotionState.STOPPED.name
                self.velocity_actual = 0.0
            elif self.target_state == InternalMotionState.STATIONARY.name:
                self.current_state = InternalMotionState.STATIONARY.name
                self.velocity_actual = 0.0
            else:
                self.current_state = MotionState.MOVING.name

        self.position_actual = utils.angle_wrap_nonnegative(
            math.degrees(self.position_actual)
        ).rad

    async def _handle_past_end_tai(self, current_tai: float) -> None:
        if self.target_state in [
            MotionState.STOPPED.name,
            MotionState.MOVING.name,
        ]:
            self.current_state = MotionState.STOPPED.name
            self.position_actual = self.position_commanded
            self.velocity_actual = 0.0
        elif self.target_state == InternalMotionState.STATIONARY.name:
            self.current_state = InternalMotionState.STATIONARY.name
            self.position_actual = self.position_commanded
            self.velocity_actual = 0.0
        else:
            diff_since_crawl_started = current_tai - self.end_tai
            self.position_actual = (
                self.start_position + self.crawl_velocity * diff_since_crawl_started
            )
            self.current_state = MotionState.CRAWLING.name
            self.velocity_actual = self.crawl_velocity
            if self.position_actual >= MAX_POSITION:
                self.position_actual = MAX_POSITION
                self.current_state = MotionState.STOPPED.name
                self.velocity_actual = 0.0
            elif self.position_actual <= MIN_POSITION:
                self.position_actual = MIN_POSITION
                self.current_state = MotionState.STOPPED.name
                self.velocity_actual = 0.0
            if math.isclose(self.crawl_velocity, 0.0):
                if self.target_state == MotionState.STOPPED.name:
                    self.current_state = MotionState.STOPPED.name
                elif self.target_state == InternalMotionState.STATIONARY.name:
                    self.current_state = InternalMotionState.STATIONARY.name

                self.velocity_actual = 0.0

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
        await self.evaluate_state(current_tai)

        # Determine the current drawn by the light wind screen motors. Here
        # fixed current values are assumed while in reality they vary depending
        # on the speed and the inclination of the light wind screen.
        if self.current_state in [MotionState.CRAWLING.name, MotionState.MOVING.name]:
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
                "status": self.current_state,
                "operationalMode": self.operational_mode.name,
            },
            "positionActual": self.position_actual,
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
            The position [rad] to move to. 0 means point to the horizon and
            pi/2 point to the zenith. These limits are not checked.
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        if not (MIN_POSITION <= position <= MAX_POSITION):
            raise ValueError(
                f"The target position {position} is outside of the "
                f"range [{MIN_POSITION, MAX_POSITION}]"
            )

        self.position_commanded = position
        self.start_position = self.position_actual
        self.crawl_velocity = 0.0
        self.start_tai = start_tai
        duration = get_duration(
            self.position_actual, self.position_commanded, self.vmax
        )
        self.end_tai = start_tai + duration
        self.target_state = MotionState.MOVING.name
        return duration

    async def crawlEl(self, velocity: float, start_tai: float) -> float:
        """Crawl the light and wind screen in the given direction at the given
        velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity [rad/s] at which to crawl. The velocity is not checked
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

        self.start_position = self.position_actual
        self.crawl_velocity = velocity
        self.vmax = velocity
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.target_state = MotionState.CRAWLING.name
        self.end_tai = start_tai
        return 0.0

    async def stopEl(self, start_tai: float) -> float:
        """Stop moving the light and wind screen.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        """
        await self._handle_moving_or_crawling(start_tai)
        self.start_position = self.position_actual
        self.position_commanded = self.position_actual
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.target_state = MotionState.STOPPED.name
        self.end_tai = start_tai
        return 0.0

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
        await self._handle_moving_or_crawling(start_tai)
        self.start_position = self.position_actual
        self.position_commanded = self.position_actual
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.target_state = InternalMotionState.STATIONARY.name
        self.end_tai = start_tai
        return 0.0

    async def exit_fault(self, start_tai: float) -> float:
        """Clear the fault state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        # self.elevation_motion.exit_fault(start_tai)
        await self._handle_moving_or_crawling(start_tai)
        self.start_position = self.position_actual
        self.position_commanded = self.position_actual
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.target_state = InternalMotionState.STATIONARY.name
        self.end_tai = start_tai
        return 0.0

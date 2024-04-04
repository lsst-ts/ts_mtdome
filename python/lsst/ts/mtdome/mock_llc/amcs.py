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
    "AmcsStatus",
    "PARK_POSITION",
    "CURRENT_PER_MOTOR_CRAWLING",
    "CURRENT_PER_MOTOR_MOVING",
    "NUM_MOTORS",
]

import logging
import math

import numpy as np
from lsst.ts import utils
from lsst.ts.xml.enums.MTDome import MotionState, OnOff

from ..enums import InternalMotionState
from ..llc_configuration_limits.amcs_limits import AmcsLimits
from .base_mock_llc import DEFAULT_MESSAGES, FAULT_MESSAGES, BaseMockStatus

# The number of motors.
NUM_MOTORS = 5

_NUM_MOTOR_TEMPERATURES = 13
_NUM_ENCODERS = 5
_NUM_RESOLVERS = 3

# Current consumption per motor when moving [A], assuming no acceleration and
# no wind gust, which is good enough for this simulator, since it ignores both.
CURRENT_PER_MOTOR_MOVING = 40.0
# Current consumption per motor when crawling [A].
CURRENT_PER_MOTOR_CRAWLING = 4.1

PARK_POSITION = 0.0

SET_ZERO_AZ_ALLOWED_STATES = [
    MotionState.PARKED.name,
    InternalMotionState.STATIONARY.name,
    MotionState.STOPPED.name,
]


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
    """Determines the duration [s] of the move using the distance of the move
    and the maximum speed.

    Parameters
    ----------
    start_position : `float`
        The start position [rad].
    end_position : `float`
        The end position [rad].
    max_speed : `float`
        The maximum speed [rad].

    Returns
    -------
    duration : `float`
        The duration of the move [s].
    """
    duration = math.fabs(get_distance(start_position, end_position)) / max_speed
    return duration


class AmcsStatus(BaseMockStatus):
    """Represents the status of the Azimuth Motion Control System in simulation
    mode.

    Parameters
    ----------
    start_tai: `float`
        The TAI time, unix seconds, at the time at which this class is
        instantiated.  To model the real dome, this should be the current time.
        However, for unit tests it can be convenient to use other values.
    """

    def __init__(self, start_tai: float) -> None:
        super().__init__()
        self.log = logging.getLogger("MockAzcsStatus")
        self.amcs_limits = AmcsLimits()

        # Default values which may be overriden by calling moveAz, crawlAz or
        # config.
        self.jmax = self.amcs_limits.jmax
        self.amax = self.amcs_limits.amax
        self.vmax = self.amcs_limits.vmax

        # Variables helping with the state of the mock AZ motion.
        self.start_position = 0.0
        self.crawl_velocity = 0.0
        self.start_tai = 0.0
        self.end_tai = 0.0

        # Variables holding the status of the mock AZ motion.
        self.messages = DEFAULT_MESSAGES
        self.fans_speed = 0.0
        self.seal_inflated = OnOff.OFF
        self.position_actual = PARK_POSITION
        self.position_commanded = PARK_POSITION
        self.velocity_actual = 0.0
        self.velocity_commanded = 0.0
        self.drive_torque_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTOR_TEMPERATURES, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_ENCODERS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_ENCODERS, dtype=float)
        self.barcode_head_raw = np.zeros(_NUM_RESOLVERS, dtype=float)
        self.barcode_head_calibrated = np.zeros(_NUM_RESOLVERS, dtype=float)
        self.barcode_head_weighted = np.zeros(_NUM_RESOLVERS, dtype=float)

        # State machine related attributes.
        self.current_state = MotionState.PARKED.name
        self.start_state = MotionState.PARKED.name
        self.target_state = MotionState.PARKED.name

        # Error state related attributes.
        self.drives_in_error_state = [False] * NUM_MOTORS

    async def evaluate_state(self, current_tai: float) -> None:
        """Evaluate the state and perform a state transition if necessary.

        Parameters
        ----------
        current_tai : `float`
            The current time, in UNIX TAI seconds.
        """
        match self.target_state:
            case (
                MotionState.MOVING.name
                | MotionState.CRAWLING.name
                | MotionState.PARKED.name
                | InternalMotionState.STATIONARY.name
            ):
                await self._handle_motion(current_tai)
            case MotionState.STOPPED.name:
                await self._handle_stopped(current_tai)
            case _:
                await self._warn_invalid_state()

    async def _warn_invalid_state(self) -> None:
        self.log.warning(f"Not handling invalid target state {self.target_state}")

    async def _handle_motion(self, current_tai: float) -> None:
        match self.current_state:
            case InternalMotionState.STATIONARY.name:
                if self.target_state in [
                    MotionState.MOVING.name,
                    MotionState.CRAWLING.name,
                    MotionState.PARKED.name,
                ]:
                    self.current_state = MotionState.DEFLATING.name
                else:
                    await self._warn_invalid_state()
            case MotionState.PARKED.name:
                if self.target_state in [
                    MotionState.MOVING.name,
                    MotionState.CRAWLING.name,
                ]:
                    self.current_state = MotionState.DEFLATING.name
                else:
                    await self._warn_invalid_state()
            case MotionState.DEFLATING.name:
                self.current_state = MotionState.DEFLATED.name
            case MotionState.DEFLATED.name:
                self.current_state = MotionState.STARTING_MOTOR_COOLING.name
            case MotionState.STARTING_MOTOR_COOLING.name:
                self.current_state = MotionState.MOTOR_COOLING_ON.name
            case MotionState.MOTOR_COOLING_ON.name:
                self.current_state = MotionState.ENABLING_MOTOR_POWER.name
            case MotionState.ENABLING_MOTOR_POWER.name:
                self.current_state = MotionState.MOTOR_POWER_ON.name
            case MotionState.MOTOR_POWER_ON.name:
                self.current_state = MotionState.GO_NORMAL.name
            case MotionState.GO_NORMAL.name:
                self.current_state = MotionState.DISENGAGING_BRAKES.name
            case MotionState.DISENGAGING_BRAKES.name:
                self.current_state = MotionState.BRAKES_DISENGAGED.name
            case MotionState.BRAKES_DISENGAGED.name:
                self.current_state = MotionState.MOVING.name
            case MotionState.MOVING.name | MotionState.CRAWLING.name:
                await self._handle_moving_or_crawling(current_tai)
            case MotionState.STOPPED.name:
                await self._handle_stopped(current_tai)
            case MotionState.ENGAGING_BRAKES.name:
                self.current_state = MotionState.BRAKES_ENGAGED.name
            case MotionState.BRAKES_ENGAGED.name:
                self.current_state = MotionState.GO_STATIONARY.name
            case MotionState.GO_STATIONARY.name:
                self.current_state = MotionState.DISABLING_MOTOR_POWER.name
            case MotionState.DISABLING_MOTOR_POWER.name:
                self.current_state = MotionState.MOTOR_POWER_OFF.name
            case MotionState.MOTOR_POWER_OFF.name:
                self.current_state = MotionState.STOPPING_MOTOR_COOLING.name
            case MotionState.STOPPING_MOTOR_COOLING.name:
                self.current_state = MotionState.MOTOR_COOLING_OFF.name
            case MotionState.MOTOR_COOLING_OFF.name:
                self.current_state = MotionState.INFLATING.name
            case MotionState.INFLATING.name:
                self.current_state = MotionState.INFLATED.name
            case MotionState.INFLATED.name:
                await self._handle_inflated()

    async def _handle_moving_or_crawling(self, current_tai: float) -> None:
        distance = get_distance(self.start_position, self.position_commanded)
        if current_tai >= self.end_tai:
            await self._handle_past_end_tai(current_tai)
        elif current_tai < self.start_tai:
            raise ValueError(
                f"Encountered TAI {current_tai} which is smaller than start TAI {self.start_tai}."
            )
        elif current_tai == self.start_tai:
            self.position_actual = self.start_position
            await self._determine_velocity_actual(distance)
        else:
            frac_time = (current_tai - self.start_tai) / (self.end_tai - self.start_tai)
            self.position_actual = self.start_position + distance * frac_time
            await self._determine_velocity_actual(distance)
        self.position_actual = utils.angle_wrap_nonnegative(
            math.degrees(self.position_actual)
        ).rad

    async def _handle_past_end_tai(self, current_tai: float) -> None:
        if self.target_state == MotionState.CRAWLING.name or not math.isclose(
            self.crawl_velocity, 0.0
        ):
            diff_since_crawl_started = current_tai - self.end_tai
            calculation_position = self.position_commanded
            if self.target_state == MotionState.CRAWLING.name:
                calculation_position = self.start_position
            self.position_actual = (
                calculation_position + self.crawl_velocity * diff_since_crawl_started
            )
            self.velocity_actual = self.crawl_velocity
            self.current_state = MotionState.CRAWLING.name
        else:
            self.position_actual = self.position_commanded
            self.velocity_actual = 0.0
            self.current_state = MotionState.STOPPED.name
            if self.start_state == MotionState.PARKING.name:
                self.target_state = MotionState.PARKED.name
            if self.start_state == MotionState.GO_STATIONARY.name:
                self.target_state = InternalMotionState.STATIONARY.name

    async def _determine_velocity_actual(self, distance: float) -> None:
        self.velocity_actual = self.vmax
        if distance < 0.0:
            self.velocity_actual = -self.vmax

    async def _handle_stopped(self, current_tai: float) -> None:
        if self.target_state in [
            MotionState.MOVING.name,
            MotionState.CRAWLING.name,
        ]:
            self.current_state = MotionState.MOVING.name
            await self._handle_moving_or_crawling(current_tai)
        elif self.target_state in [
            MotionState.PARKED.name,
            InternalMotionState.STATIONARY.name,
        ]:
            self.current_state = MotionState.ENGAGING_BRAKES
        elif self.target_state == MotionState.STOPPED.name:
            self.current_state = MotionState.STOPPED.name
            await self._handle_moving_or_crawling(current_tai)
        else:
            await self._warn_invalid_state()

    async def _handle_inflated(self) -> None:
        if self.target_state == MotionState.PARKED.name:
            self.current_state = MotionState.PARKED.name
        elif self.target_state == InternalMotionState.STATIONARY.name:
            self.current_state = InternalMotionState.STATIONARY.name
        else:
            await self._warn_invalid_state()

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

        # Determine the current drawn by the azimuth motors. Here fixed current
        # values are assumed while in reality they vary depending on the speed.
        if self.current_state == MotionState.MOVING.name:
            self.drive_current_actual = np.full(
                NUM_MOTORS, CURRENT_PER_MOTOR_MOVING, dtype=float
            )
        elif self.current_state == MotionState.CRAWLING.name:
            self.drive_current_actual = np.full(
                NUM_MOTORS, CURRENT_PER_MOTOR_CRAWLING, dtype=float
            )
        else:
            self.drive_current_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": self.current_state,
                "fans": self.fans_speed,
                "inflate": self.seal_inflated.value,
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
            "barcodeHeadRaw": self.barcode_head_raw.tolist(),
            "barcodeHeadCalibrated": self.barcode_head_calibrated.tolist(),
            "barcodeHeadWeighted": self.barcode_head_weighted.tolist(),
            "appliedConfiguration": {
                "jmax": self.jmax,
                "amax": self.amax,
                "vmax": self.vmax,
            },
            "timestampUTC": current_tai,
        }

        self.log.debug(f"{current_tai=}, amcs_state = {self.llc_status}")

    async def moveAz(self, position: float, velocity: float, start_tai: float) -> float:
        """Move the dome at maximum velocity to the specified azimuth. Azimuth
        is measured from 0 at north via 90 at east and 180 at south to 270 west
        and 360 = 0. The value of azimuth is not checked for the range between
        0 and 360.

        Parameters
        ----------
        position: `float`
            The azimuth  [rad] to move to.
        velocity: `float`
            The velocity [rad/s] at which to crawl once the commanded azimuth
            has been reached at maximum velocity. The velocity is not checked
            against the velocity limits for the dome.
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        self.position_commanded = position
        self.start_position = self.position_actual
        self.crawl_velocity = velocity
        self.start_tai = start_tai
        duration = get_duration(
            self.position_actual, self.position_commanded, self.vmax
        )
        self.end_tai = start_tai + duration
        self.start_state = self.current_state
        self.target_state = MotionState.MOVING.name
        return duration

    async def crawlAz(self, velocity: float, start_tai: float) -> float:
        """Crawl the dome in the given direction at the given velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity [rad/s] at which to crawl. The velocity is not checked
            against the velocity limits for the dome.
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        if velocity >= 0:
            # make sure that the dome never stops moving
            self.position_commanded = math.inf
        else:
            # make sure that the dome never stops moving
            self.position_commanded = -math.inf
        self.start_position = self.position_actual
        self.crawl_velocity = velocity
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.start_state = self.current_state
        self.target_state = MotionState.CRAWLING.name
        return 0.0

    async def stopAz(self, start_tai: float) -> float:
        """Stop all motion of the dome.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        await self._handle_moving_or_crawling(start_tai)
        self.start_position = self.position_actual
        self.position_commanded = self.position_actual
        self.crawl_velocity = 0.0
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.start_state = self.current_state
        self.target_state = MotionState.STOPPED.name
        return 0.0

    async def park(self, start_tai: float) -> float:
        """Park the dome by moving it to azimuth 0.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        self.position_commanded = PARK_POSITION
        self.start_position = self.position_actual
        self.crawl_velocity = 0.0
        self.start_tai = start_tai
        duration = get_duration(
            self.position_actual, self.position_commanded, self.vmax
        )
        self.end_tai = start_tai + duration
        self.start_state = MotionState.PARKING.name
        self.target_state = MotionState.MOVING.name
        return duration

    async def go_stationary(self, start_tai: float) -> float:
        """Stop azimuth motion and engage the brakes. Also disengage the
        locking pins if engaged.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        await self._handle_moving_or_crawling(start_tai)
        self.start_position = self.position_actual
        self.position_commanded = self.position_actual
        self.crawl_velocity = 0.0
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.start_state = MotionState.GO_STATIONARY.name
        self.target_state = MotionState.STOPPED.name
        return 0.0

    async def inflate(self, start_tai: float, action: str) -> float:
        """Inflate or deflate the inflatable seal.

        This is a placeholder for now until it becomes clear what this command
        is supposed to do.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        action: `str`
            The value should be ON or OFF but the value doesn't get validated
            here.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        self.seal_inflated = OnOff(action)
        duration = 0.0
        self.end_tai = start_tai
        return duration

    async def fans(self, start_tai: float, speed: float) -> float:
        """Enable or disable the fans in the dome.

        This is a placeholder for now until it becomes clear what this command
        is supposed to do.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        speed: `float`
            The speed of the fans [%].

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        self.fans_speed = speed
        duration = 0.0
        self.end_tai = start_tai
        return duration

    async def exit_fault(self, start_tai: float) -> float:
        """Clear the fault state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        if any(self.drives_in_error_state):
            raise RuntimeError("Make sure to reset drives before exiting from fault.")

        self.start_tai = start_tai
        self.start_position = self.position_actual
        self.position_commanded = self.position_actual
        self.current_state = InternalMotionState.STATIONARY.name
        self.start_state = InternalMotionState.STATIONARY.name
        self.target_state = InternalMotionState.STATIONARY.name
        self.crawl_velocity = 0.0
        self.end_tai = start_tai
        self.messages = DEFAULT_MESSAGES
        return 0.0

    async def reset_drives_az(self, start_tai: float, reset: list[int]) -> float:
        """Reset one or more AZ drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        reset: array of int
            Desired reset action to execute on each AZ drive: 0 means don't
            reset, 1 means reset.

        Returns
        -------
        `float`
            The expected duration of the command [s].

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        for motor_id, val in enumerate(reset):
            if val == 1:
                self.drives_in_error_state[motor_id] = False
        self.end_tai = start_tai
        return 0.0

    async def set_zero_az(self, start_tai: float) -> float:
        """Take the current position of the dome as zero. This is necessary as
        long as the racks and pinions on the drives have not been installed yet
        to compensate for slippage of the drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        if self.current_state not in SET_ZERO_AZ_ALLOWED_STATES:
            raise RuntimeError(
                f"AMCS is in {self.current_state} and needs to be in "
                f"{SET_ZERO_AZ_ALLOWED_STATES}."
            )
        self.start_position = 0.0
        self.crawl_velocity = 0.0
        self.position_commanded = 0.0
        self.velocity_commanded = 0.0
        self.start_tai = start_tai
        self.end_tai = start_tai
        self.start_state = self.current_state
        self.target_state = self.current_state
        return 0.0

    async def set_fault(self, start_tai: float, drives_in_error: list[int]) -> None:
        """Set the MotionState of AMCS to fault and set the drives in
        drives_in_error to error.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        drives_in_error : array of int
            Desired error action to execute on each AZ drive: 0 means don't
            set to error, 1 means set to error.

        Notes
        -----
        This function is not mapped to a command that MockMTDomeController can
        receive. It is intended to be set by unit test cases.
        """
        await self._handle_moving_or_crawling(start_tai)
        for motor_id, val in enumerate(drives_in_error):
            if val == 1:
                self.drives_in_error_state[motor_id] = True
        self.velocity_actual = 0.0
        self.velocity_commanded = 0.0
        self.start_state = MotionState.ERROR.name
        self.current_state = MotionState.ERROR.name
        self.target_state = MotionState.ERROR.name
        self.messages = FAULT_MESSAGES

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

__all__ = ["AmcsStatus", "PARK_POSITION"]

import logging
import math
import typing

import numpy as np

from .base_mock_llc import BaseMockStatus
from ..llc_configuration_limits.amcs_limits import AmcsLimits
from ..enums import LlcMotionState, OnOff
from .mock_motion.azimuth_motion import AzimuthMotion

_NUM_MOTORS = 5
_NUM_MOTOR_TEMPERATURES = 13
_NUM_ENCODERS = 5
_NUM_RESOLVERS = 3

PARK_POSITION = 0.0


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
        # config
        self.jmax = self.amcs_limits.jmax
        self.amax = self.amcs_limits.amax
        self.vmax = self.amcs_limits.vmax

        # Variables helping with the state of the mock AZ motion
        self.azimuth_motion = AzimuthMotion(
            start_position=PARK_POSITION, max_speed=self.vmax, start_tai=start_tai
        )

        # Keep the end TAI time as a reference for unit tests
        self.end_tai = 0.0

        # Variables holding the status of the mock AZ motion.
        # For now the value of 'messages' is kept as is since the error codes
        # and descriptions still are being discussed.
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.fans_enabled = OnOff.OFF
        self.seal_inflated = OnOff.OFF
        self.position_commanded = PARK_POSITION
        self.velocity_commanded = PARK_POSITION
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTOR_TEMPERATURES, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_ENCODERS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_ENCODERS, dtype=float)
        self.barcode_head_raw = np.zeros(_NUM_RESOLVERS, dtype=float)
        self.barcode_head_calibrated = np.zeros(_NUM_RESOLVERS, dtype=float)
        self.barcode_head_weighted = np.zeros(_NUM_RESOLVERS, dtype=float)

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
        ) = self.azimuth_motion.get_position_velocity_and_motion_state(tai=current_tai)
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": motion_state.name,
                "fans": self.fans_enabled.value,
                "inflate": self.seal_inflated.value,
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

        self.log.debug(f"amcs_state = {self.llc_status}")

    async def moveAz(self, position: float, velocity: float, start_tai: float) -> float:
        """Move the dome at maximum velocity to the specified azimuth. Azimuth
        is measured from 0 at north via 90 at east and 180 at south to 270 west
        and 360 = 0. The value of azimuth is not checked for the range between
        0 and 360.

        Parameters
        ----------
        position: `float`
            The azimuth (deg) to move to.
        velocity: `float`
            The velocity (deg/s) at which to crawl once the commanded azimuth
            has been reached at maximum velocity. The velocity is not checked
            against the velocity limits for the dome.
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        self.log.debug(f"moveAz with position={position} and velocity={velocity}")
        self.position_commanded = position
        duration = self.azimuth_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=position,
            crawl_velocity=velocity,
            motion_state=LlcMotionState.MOVING,
        )
        self.end_tai = start_tai + duration
        return duration

    async def crawlAz(self, velocity: float, start_tai: float) -> float:
        """Crawl the dome in the given direction at the given velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked
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
        duration = self.azimuth_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=self.position_commanded,
            crawl_velocity=velocity,
            motion_state=LlcMotionState.CRAWLING,
        )
        self.end_tai = start_tai + duration
        return duration

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
        duration = self.azimuth_motion.stop(start_tai)
        self.end_tai = start_tai + duration
        return duration

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
        duration = self.azimuth_motion.park(start_tai)
        self.end_tai = start_tai + duration
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
        duration = self.azimuth_motion.go_stationary(start_tai)
        self.end_tai = start_tai + duration
        return duration

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

    async def fans(self, start_tai: float, action: str) -> float:
        """Enable or disable the fans in the dome.

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
        self.fans_enabled = OnOff(action)
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
        duration = self.azimuth_motion.exit_fault(start_tai)
        self.end_tai = start_tai + duration
        return duration

    async def reset_drives_az(self, start_tai: float, reset: typing.List[int]) -> float:
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
        duration = self.azimuth_motion.reset_drives_az(start_tai, reset)
        self.end_tai = start_tai + duration
        return duration

    async def calibrate_az(self, start_tai: float) -> float:
        """Take the current position of the dome as zero. This is necessary as
        long as the racks and pinions on the drives have not been installed yet
        to compensate for slippage of the drives.

        Returns
        -------
        `float`
            The expected duration of the command [s].

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        self.azimuth_motion.calibrate_az(start_tai)
        duration = 0.0
        self.end_tai = start_tai + duration
        return duration

    async def set_fault(
        self, start_tai: float, drives_in_error: typing.List[int]
    ) -> None:
        """Set the LlcMotionState of AMCS to fault and set the drives in
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
        self.azimuth_motion.set_fault(start_tai, drives_in_error)

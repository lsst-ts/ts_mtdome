# This file is part of ts_MTDome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the Vera Rubin Observatory
# Project (https://www.lsst.org).
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

__all__ = ["AmcsStatus"]

import logging
import math

import numpy as np

from .base_mock_llc import BaseMockStatus
from ..llc_configuration_limits.amcs_limits import AmcsLimits
from lsst.ts.idl.enums.MTDome import MotionState
from .mock_motion.azimuth_motion import AzimuthMotion
from ..on_off import OnOff

_NUM_MOTORS = 5
_NUM_ENCODERS = 5
_NUM_RESOLVERS = 3


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

    def __init__(self, start_tai):
        super().__init__()
        self.log = logging.getLogger("MockAzcsStatus")
        self.amcs_limits = AmcsLimits()
        # default values which may be overriden by calling moveAz, crawlAz or
        # config
        self.jmax = self.amcs_limits.jmax
        self.amax = self.amcs_limits.amax
        self.vmax = self.amcs_limits.vmax
        # variables helping with the state of the mock AZ motion
        self.azimuth_motion = AzimuthMotion(
            start_position=0.0, max_speed=self.vmax, start_tai=start_tai
        )
        self.duration = 0.0
        # variables holding the status of the mock AZ motion. The error codes
        # will be specified in a future Dome Software meeting.
        self.status = MotionState.STOPPED
        self.error = ["No Error"]
        self.fans_enabled = OnOff.OFF
        self.seal_inflated = OnOff.OFF
        self.position_commanded = 0
        self.velocity_commanded = 0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_ENCODERS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_ENCODERS, dtype=float)
        self.resolver_raw = np.zeros(_NUM_RESOLVERS, dtype=float)
        self.resolver_calibrated = np.zeros(_NUM_RESOLVERS, dtype=float)

    async def determine_status(self, current_tai):
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
                "error": self.error,
                "status": motion_state.name,
                "fans": self.fans_enabled.value,
                "inflate": self.seal_inflated.value,
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
            # DM-26653: The name of this key is still under discussion and
            # could be modified to "timestampUTC"
            "timestampUTC": current_tai,
        }

        self.log.debug(f"amcs_state = {self.llc_status}")

    async def moveAz(self, position, velocity, start_tai):
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
        self.duration = self.azimuth_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=position,
            crawl_velocity=velocity,
            motion_state=MotionState.MOVING,
        )
        return self.duration

    async def crawlAz(self, velocity, start_tai):
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
        """
        if velocity >= 0:
            # make sure that the dome never stops moving
            self.position_commanded = math.inf
        else:
            # make sure that the dome never stops moving
            self.position_commanded = -math.inf
        self.duration = self.azimuth_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=self.position_commanded,
            crawl_velocity=velocity,
            motion_state=MotionState.CRAWLING,
        )
        return self.duration

    async def stopAz(self, start_tai):
        """Stop all motion of the dome.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        self.azimuth_motion.stop(start_tai)
        self.duration = 0.0
        return self.duration

    async def park(self, start_tai):
        """Park the dome by moving it to azimuth 0.


        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        """
        self.status = MotionState.PARKING
        self.position_commanded = 0.0
        self.duration = self.azimuth_motion.park(start_tai)
        return self.duration

    async def inflate(self, action):
        """Inflate or deflate the inflatable seal.

        This is a placeholder for now until it becomes clear what this command
        is supposed to do.

        Parameters
        ----------
        action: `str`
            The value should be ON or OFF but the value doesn't get validated
            here.
        """
        self.seal_inflated = OnOff(action)
        self.duration = 0.0
        return self.duration

    async def fans(self, action):
        """Enable or disable the fans in the dome.

        This is a placeholder for now until it becomes clear what this command
        is supposed to do.

        Parameters
        ----------
        action: `str`
            The value should be ON or OFF but the value doesn't get validated
            here.
        """
        self.fans_enabled = OnOff(action)
        self.duration = 0.0
        return self.duration

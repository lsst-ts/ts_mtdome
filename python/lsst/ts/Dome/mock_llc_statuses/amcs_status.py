import logging
import math

import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from ..llc_configuration_limits.amcs_limits import AmcsLimits
from ..llc_status import LlcStatus

_NUM_MOTORS = 5


class AmcsStatus(BaseMockStatus):
    """Represents the status of the Azimuth Motion Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockAzcsStatus")
        self.amcs_limits = AmcsLimits()
        # default values which may be overriden by calling moveAz, crawlAz of config
        self.jmax = self.amcs_limits.jmax
        self.amax = self.amcs_limits.amax
        self.vmax = self.amcs_limits.vmax
        # variables helping with the state of the mock AZ motion
        self.motion_velocity = self.vmax
        self.crawl_velocity = 0
        self.seal_inflated = False
        self.fans_enabled = False
        # variables holding the status of the mock AZ motion
        self.status = LlcStatus.STOPPED.value
        self.position_orig = 0.0
        self.position_error = 0.0
        self.position_actual = 0
        self.position_cmd = 0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_error = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_cmd = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temp_actual = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_calibrated = np.zeros(_NUM_MOTORS, dtype=float)

    async def determine_status(self, current_tai):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        time_diff = float(current_tai - self.command_time_tai)
        self.log.debug(
            f"current_tai = {current_tai}, self.command_time_tai = {self.command_time_tai}, "
            f"time_diff = {time_diff}"
        )
        if self.status != LlcStatus.STOPPED.value:
            azimuth_step = self.motion_velocity * time_diff
            self.position_actual = self.position_orig + azimuth_step
            if self.motion_velocity >= 0:
                if self.position_actual >= self.position_cmd:
                    self.position_actual = self.position_cmd
                    if self.status == LlcStatus.MOVING.value:
                        if self.crawl_velocity >= 0:
                            self.position_cmd = math.radians(720)
                        else:
                            self.position_cmd = math.radians(-360)
                        self.motion_velocity = self.crawl_velocity
                        self.status = LlcStatus.CRAWLING.value
                    else:
                        self.position_cmd = self.position_actual
                        self.motion_velocity = 0
                        self.status = LlcStatus.PARKED.value
            else:
                if self.position_actual <= self.position_cmd:
                    self.position_actual = self.position_cmd
                    if self.status == LlcStatus.MOVING.value:
                        if self.crawl_velocity >= 0:
                            self.position_cmd = math.radians(720)
                        else:
                            self.position_cmd = math.radians(-360)
                        self.motion_velocity = self.crawl_velocity
                        self.status = LlcStatus.STOPPED.value
                    else:
                        self.position_cmd = self.position_actual
                        self.motion_velocity = 0
                        self.status = LlcStatus.PARKED.value
        self.llc_status = {
            "status": self.status,
            "positionError": self.position_error,
            "positionActual": self.position_actual,
            "positionCmd": self.position_cmd,
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueError": self.drive_torque_error.tolist(),
            "driveTorqueCmd": self.drive_torque_cmd.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTempActual": self.drive_temp_actual.tolist(),
            "encoderHeadRaw": self.encoder_head_raw.tolist(),
            "encoderHeadCalibrated": self.encoder_head_calibrated.tolist(),
            "resolverRaw": self.resolver_raw.tolist(),
            "resolverCalibrated": self.resolver_calibrated.tolist(),
        }
        self.log.debug(f"amcs_state = {self.llc_status}")

    async def moveAz(self, azimuth, velocity):
        """Move the dome at maximum velocity to the specified azimuth. Azimuth is measured from 0 at
            north via 90 at east and 180 at south to 270 west and 360 = 0. The value of azimuth is not
            checked for the range between 0 and 360.

        Parameters
        ----------
        azimuth: `float`
            The azimuth to move to.
        velocity: `float`
            The velocity (deg/s) at which to crawl once the commanded azimuth has been reached at maximum
            velocity. The velocity is not checked against the velocity limits for the dome.
        """
        self.status = LlcStatus.MOVING.value
        self.position_orig = self.position_actual
        self.command_time_tai = salobj.current_tai()
        self.position_cmd = azimuth
        self.crawl_velocity = velocity
        self.motion_velocity = self.vmax
        if self.position_cmd < self.position_actual:
            self.motion_velocity = -self.vmax

    async def crawlAz(self, velocity):
        """Crawl the dome in the given direction at the given velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked against the velocity limits
            for the dome.
        """
        self.position_orig = self.position_actual
        self.command_time_tai = salobj.current_tai()
        self.motion_velocity = velocity
        self.status = LlcStatus.CRAWLING.value
        if self.motion_velocity >= 0:
            self.position_cmd = math.radians(720)
        else:
            self.position_cmd = math.radians(-360)

    async def stopAz(self):
        """Stop all motion of the dome.
        """
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.STOPPED.value

    async def park(self):
        """Park the dome, meaning that it will be moved to azimuth 0.
        """
        self.status = LlcStatus.PARKING.value
        self.position_orig = self.position_actual
        self.command_time_tai = salobj.current_tai()
        self.position_cmd = 0.0
        self.motion_velocity = -self.vmax

    async def inflate(self, action):
        """Inflate or deflate the inflatable seal.

        This is a placeholder for now until it becomes clear what this command is supposed to do.

        Parameters
        ----------
        action: `bool`
            The value should be True or False but the value doesn't get validated here.
        """
        self.command_time_tai = salobj.current_tai()
        self.seal_inflated = action

    async def fans(self, action):
        """Enable or disable the fans in the dome.

        This is a placeholder for now until it becomes clear what this command is supposed to do.

        Parameters
        ----------
        action: `bool`
            The value should be True or False but the value doesn't get validated here.
        """
        self.command_time_tai = salobj.current_tai()
        self.fans_enabled = action

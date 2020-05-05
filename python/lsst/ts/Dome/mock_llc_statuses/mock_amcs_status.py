import logging
import math

from .base_mock_status import BaseMockStatus
from lsst.ts.Dome.llc_configuration_limits.amcs_configuration_limits import (
    AmcsConfigurationLimits,
)


class MockAmcsStatus(BaseMockStatus):
    """Represents the status of the Azimuth Motion Control System in simulation mode.

    Parameters
    ----------
    period: `float`
        The period in decimal seconds determining how often the status of this Lower Level Component will
        be updated.
    """

    def __init__(self, period):
        super().__init__()
        self.log = logging.getLogger("MockAzcsStatus")
        self.az_limits = AmcsConfigurationLimits()
        self.period = period
        # default values which may be overriden by calling moveAz, crawlAz of config
        self.jmax = self.az_limits.jmax
        self.amax = self.az_limits.amax
        self.vmax = self.az_limits.vmax
        # variables helping with the state of the mock AZ motion
        self.motion_velocity = self.vmax
        self.motion_direction = "CW"
        # variables holding the status of the mock AZ motion
        self.status = "Stopped"
        self.position_error = 0.0
        self.position_actual = 0
        self.position_cmd = 0
        self.drive_torque_actual = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.drive_torque_error = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.drive_torque_cmd = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.drive_current_actual = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.drive_temp_actual = [20.0, 20.0, 20.0, 20.0, 20.0]
        self.encoder_head_raw = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.encoder_head_calibrated = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.resolver_raw = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.resolver_calibrated = [0.0, 0.0, 0.0, 0.0, 0.0]

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        if self.status != "Stopped":
            azimuth_step = self.motion_velocity * self.period
            if self.motion_direction == "CW":
                self.position_actual = self.position_actual + azimuth_step
                if self.position_actual >= self.position_cmd:
                    self.position_actual = self.position_cmd
                    if self.status == "Moving":
                        self.status = "Stopped"
                    else:
                        self.status = "Parked"
            else:
                self.position_actual = self.position_actual - azimuth_step
                if self.position_actual <= self.position_cmd:
                    self.position_actual = self.position_cmd
                    if self.status == "Moving":
                        self.status = "Stopped"
                    else:
                        self.status = "Parked"
        self.llc_status = {
            "status": self.status,
            "positionError": self.position_error,
            "positionActual": self.position_actual,
            "positionCmd": self.position_cmd,
            "driveTorqueActual": self.drive_torque_actual,
            "driveTorqueError": self.drive_torque_error,
            "driveTorqueCmd": self.drive_torque_cmd,
            "driveCurrentActual": self.drive_current_actual,
            "driveTempActual": self.drive_temp_actual,
            "encoderHeadRaw": self.encoder_head_raw,
            "encoderHeadCalibrated": self.encoder_head_calibrated,
            "resolverRaw": self.resolver_raw,
            "resolverCalibrated": self.resolver_calibrated,
        }
        self.log.debug(f"amcs_state = {self.llc_status}")

    async def moveAz(self, azimuth):
        """Mock moving of the dome at maximum velocity to the specified azimuth. Azimuth is measured from 0 at
            north via 90 at east and 180 at south to 270 west and 360 = 0. The value of azimuth is not
            checked for the range between 0 and 360.

        Parameters
        ----------
        azimuth: `float`
            The azimuth to move to.
        """
        self.position_cmd = azimuth
        self.motion_velocity = self.vmax
        self.status = "Moving"
        if self.position_cmd >= self.position_actual:
            self.motion_direction = "CW"
        else:
            self.motion_direction = "CCW"

    async def crawlAz(self, direction, velocity):
        """Mock crawling of the dome in the given direction at the given velocity.

        Parameters
        ----------
        direction: `str`
            The string should be CW (clockwise) or CCW (counter clockwise) but the actual value doesn't get
            checked. If it is not CW then CCW is assumed.
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked against the velocity limits
            for the dome.
        """
        self.motion_direction = direction
        self.motion_velocity = velocity
        self.status = "Crawling"
        if self.motion_direction == "CW":
            self.position_cmd = math.inf
        else:
            self.position_cmd = -math.inf

    async def stopAz(self):
        """Mock stopping all motion of the dome.
        """
        self.status = "Stopped"

    async def park(self):
        """Mock parking of the dome, meaning that it will be moved to azimuth 0.
        """
        self.position_cmd = 0.0
        self.motion_velocity = self.vmax
        self.status = "Parking"
        self.motion_direction = "CCW"

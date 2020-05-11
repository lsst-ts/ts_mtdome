import logging
import math
import numpy as np

from .base_mock_status import BaseMockStatus
from ..llc_configuration_limits.amcs_limits import AmcsLimits
from ..azcs_motion_direction import AzcsMotionDirection as motion_dir
from ..llc_status import LlcStatus

NUM_MOTORS = 5


class AmcsStatus(BaseMockStatus):
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
        self.amcs_limits = AmcsLimits()
        self.period = period
        # default values which may be overriden by calling moveAz, crawlAz of config
        self.jmax = self.amcs_limits.jmax
        self.amax = self.amcs_limits.amax
        self.vmax = self.amcs_limits.vmax
        # variables helping with the state of the mock AZ motion
        self.motion_velocity = self.vmax
        self.motion_direction = motion_dir.CW.value
        self.seal_inflated = False
        self.fans_enabled = False
        # variables holding the status of the mock AZ motion
        self.status = LlcStatus.STOPPED.value
        self.position_error = 0.0
        self.position_actual = 0
        self.position_cmd = 0
        self.drive_torque_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_torque_error = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_torque_cmd = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(NUM_MOTORS, dtype=float)
        self.drive_temp_actual = np.full(NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(NUM_MOTORS, dtype=float)
        self.resolver_raw = np.zeros(NUM_MOTORS, dtype=float)
        self.resolver_calibrated = np.zeros(NUM_MOTORS, dtype=float)

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        # TODO Make sure that radians are used because that is what the real LLCs will use as well. DM-24789
        if self.status != LlcStatus.STOPPED.value:
            azimuth_step = self.motion_velocity * self.period
            if self.motion_direction == motion_dir.CW.value:
                self.position_actual = self.position_actual + azimuth_step
                if self.position_actual >= self.position_cmd:
                    self.position_actual = self.position_cmd
                    if self.status == LlcStatus.MOVING.value:
                        self.status = LlcStatus.STOPPED.value
                    else:
                        self.status = LlcStatus.PARKED.value
            else:
                self.position_actual = self.position_actual - azimuth_step
                if self.position_actual <= self.position_cmd:
                    self.position_actual = self.position_cmd
                    if self.status == LlcStatus.MOVING.value:
                        self.status = LlcStatus.STOPPED.value
                    else:
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

    async def moveAz(self, azimuth):
        """Mock moving of the dome at maximum velocity to the specified azimuth. Azimuth is measured from 0 at
            north via 90 at east and 180 at south to 270 west and 360 = 0. The value of azimuth is not
            checked for the range between 0 and 360.

        Parameters
        ----------
        azimuth: `float`
            The azimuth to move to.
        """
        # TODO Make sure that radians are used because that is what the real LLCs will use as well. DM-24789
        self.position_cmd = azimuth
        self.motion_velocity = self.vmax
        self.status = LlcStatus.MOVING.value
        if self.position_cmd >= self.position_actual:
            self.motion_direction = motion_dir.CW.value
        else:
            self.motion_direction = motion_dir.CCW.value

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
        # TODO Make sure that radians are used because that is what the real LLCs will use as well. DM-24789
        self.motion_direction = direction
        self.motion_velocity = velocity
        self.status = LlcStatus.CRAWLING.value
        if self.motion_direction == motion_dir.CW.value:
            self.position_cmd = math.inf
        else:
            self.position_cmd = -math.inf

    async def stopAz(self):
        """Mock stopping all motion of the dome.
        """
        self.status = LlcStatus.STOPPED.value

    async def park(self):
        """Mock parking of the dome, meaning that it will be moved to azimuth 0.
        """
        self.position_cmd = 0.0
        self.motion_velocity = self.vmax
        self.status = LlcStatus.PARKING.value
        self.motion_direction = motion_dir.CCW.value

    async def inflate(self, action):
        """Inflate or deflate the inflatable seal.

        This is a placeholder for now until it becomes clear what this command is supposed to do.

        Parameters
        ----------
        action: `bool`
            The value should be True or False but the value doesn't get validated here.
        """
        self.seal_inflated = action

    async def fans(self, action):
        """Enable or disable the fans in the dome.

        This is a placeholder for now until it becomes clear what this command is supposed to do.

        Parameters
        ----------
        action: `bool`
            The value should be True or False but the value doesn't get validated here.
        """
        self.fans_enabled = action

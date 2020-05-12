import logging
import numpy as np

from .base_mock_status import BaseMockStatus
from ..llc_configuration_limits.lwscs_limits import LwscsLimits
from ..lwscs_motion_direction import LwcsMotionDirection as motion_dir
from ..llc_status import LlcStatus

_NUM_MOTORS = 2


class LwscsStatus(BaseMockStatus):
    """Represents the status of the Light and Wind Screen Control System in simulation mode.

    Parameters
    ----------
    period: `float`
        The period in decimal seconds determining how often the status of this Lower Level Component will
        be updated.
    """

    def __init__(self, period):
        super().__init__()
        self.log = logging.getLogger("MockLwscsStatus")
        self.lwscs_limits = LwscsLimits()
        self.period = period
        # default values which may be overriden by calling moveEl, crawlEl of config
        self.jmax = self.lwscs_limits.jmax
        self.amax = self.lwscs_limits.amax
        self.vmax = self.lwscs_limits.vmax
        # variables helping with the state of the mock EL motion
        self.motion_velocity = self.vmax
        self.motion_direction = motion_dir.UP.value
        # variables holding the status of the mock EL motion
        self.status = LlcStatus.STOPPED.value
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
        self.power_absortion = 0.0

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        # TODO Make sure that radians are used because that is what the real LLCs will use as well. DM-24789
        if self.status != LlcStatus.STOPPED.value:
            elevation_step = self.motion_velocity * self.period
            if self.motion_direction == motion_dir.UP.value:
                self.position_actual = self.position_actual + elevation_step
                if self.position_actual >= self.position_cmd:
                    self.position_actual = self.position_cmd
                    self.status = LlcStatus.STOPPED.value
            else:
                self.position_actual = self.position_actual - elevation_step
                if self.position_actual <= self.position_cmd:
                    self.position_actual = self.position_cmd
                    self.status = LlcStatus.STOPPED.value
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
            "powerAbsortion": self.power_absortion,
        }
        self.log.debug(f"lwscs_state = {self.llc_status}")

    async def moveEl(self, elevation):
        """Mock moving the light and wind screen to the given elevation.

        Parameters
        ----------
        elevation: `float`
            The elevation (deg) to move to. 0 means point to the horizon and 180 point to the zenith. These
            limits are not checked.
        """
        # TODO Make sure that radians are used because that is what the real LLCs will use as well. DM-24789
        self.position_cmd = elevation
        self.motion_velocity = self.vmax
        self.status = LlcStatus.MOVING.value
        if self.position_cmd >= self.position_actual:
            self.motion_direction = motion_dir.UP.value
        else:
            self.motion_direction = motion_dir.DOWN.value

    async def crawlEl(self, direction, velocity):
        """Mock crawling of the light and wind screen in the given direction at the given velocity.

        Parameters
        ----------
        direction: `str`
            The string should be UP or DOWN but the actual value doesn't get checked. If it is not UP then
            DOWN is assumed.
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked against the velocity limits
            for the light and wind screen.
        """
        # TODO Make sure that radians are used because that is what the real LLCs will use as well. DM-24789
        self.motion_direction = direction
        self.motion_velocity = velocity
        self.status = LlcStatus.CRAWLING.value
        if self.motion_direction == motion_dir.UP.value:
            self.position_cmd = 90
        else:
            self.position_cmd = 0

    async def stopEl(self):
        self.status = LlcStatus.STOPPED.value

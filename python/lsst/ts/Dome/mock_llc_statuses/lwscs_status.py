__all__ = ["LwscsLimits"]

import logging
import math

import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from ..llc_configuration_limits.lwscs_limits import LwscsLimits
from ..llc_status import LlcStatus

_NUM_MOTORS = 2


class LwscsStatus(BaseMockStatus):
    """Represents the status of the Light and Wind Screen Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockLwscsStatus")
        self.lwscs_limits = LwscsLimits()
        # default values which may be overriden by calling moveEl, crawlEl of config
        self.jmax = self.lwscs_limits.jmax
        self.amax = self.lwscs_limits.amax
        self.vmax = self.lwscs_limits.vmax
        # variables helping with the state of the mock EL motion
        self.motion_velocity = self.vmax
        # variables holding the status of the mock EL motion
        self.status = LlcStatus.STOPPED
        self.position_orig = 0.0
        self.position_actual = 0
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

    async def determine_status(self, current_tai):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        time_diff = float(current_tai - self.command_time_tai)
        if self.status != LlcStatus.STOPPED:
            elevation_step = self.motion_velocity * time_diff
            self.position_actual = self.position_orig + elevation_step
            if self.motion_velocity >= 0:
                if self.position_actual >= self.position_commanded:
                    self.position_orig = self.position_actual
                    self.position_actual = self.position_commanded
                    self.status = LlcStatus.STOPPED
            else:
                if self.position_actual <= self.position_commanded:
                    self.position_orig = self.position_actual
                    self.position_actual = self.position_commanded
                    self.status = LlcStatus.STOPPED
        self.llc_status = [
            {
                "status": self.status.value,
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
                "timestamp": current_tai,
            }
        ]
        self.log.debug(f"lwscs_state = {self.llc_status}")

    async def moveEl(self, position):
        """Move the light and wind screen to the given elevation.

        Parameters
        ----------
        position: `float`
            The position (deg) to move to. 0 means point to the horizon and 180 point to the zenith. These
            limits are not checked.
        """
        self.status = LlcStatus.MOVING
        self.position_orig = self.position_actual
        self.command_time_tai = salobj.current_tai()
        self.position_commanded = position
        self.motion_velocity = self.vmax
        if self.position_commanded < self.position_actual:
            self.motion_velocity = -self.vmax

    async def crawlEl(self, velocity):
        """Crawl the light and wind screen in the given direction at the given velocity.

        Parameters
        ----------
        velocity: `float`
            The velocity (deg/s) at which to crawl. The velocity is not checked against the velocity limits
            for the light and wind screen.
        """
        self.position_orig = self.position_actual
        self.command_time_tai = salobj.current_tai()
        self.motion_velocity = velocity
        self.status = LlcStatus.CRAWLING
        if self.motion_velocity >= 0:
            self.position_commanded = math.radians(90)
        else:
            self.position_commanded = 0

    async def stopEl(self):
        """Stop moving the light and wind screen.
        """
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.STOPPED

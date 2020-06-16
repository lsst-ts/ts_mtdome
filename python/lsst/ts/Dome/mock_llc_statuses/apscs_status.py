__all__ = ["ApscsStatus"]

import logging
import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from ..llc_status import LlcStatus

_NUM_MOTORS = 4


class ApscsStatus(BaseMockStatus):
    """Represents the status of the Aperture Shutter Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockApscsStatus")
        # variables holding the status of the mock Aperture Shutter
        self.status = LlcStatus.CLOSED
        self.position_actual = 0.0
        self.position_commanded = 0.0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.resolver_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.power_draw = 0.0

    async def determine_status(self, current_tai):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        time_diff = current_tai - self.command_time_tai
        self.log.debug(
            f"current_tai = {current_tai}, self.command_time_tai = {self.command_time_tai}, "
            f"time_diff = {time_diff}"
        )
        self.llc_status = [
            {
                "status": self.status.value,
                "positionActual": self.position_actual,
                "positionCommanded": self.position_commanded,
                "driveTorqueActual": self.drive_torque_actual.tolist(),
                "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
                "driveCurrentActual": self.drive_current_actual.tolist(),
                "driveTemperature": self.drive_temperature.tolist(),
                "resolverHeadRaw": self.resolver_head_raw.tolist(),
                "resolverHeadCalibrated": self.resolver_head_calibrated.tolist(),
                "powerDraw": self.power_draw,
                "timestamp": current_tai,
            }
        ]
        self.log.debug(f"apcs_state = {self.llc_status}")

    async def openShutter(self):
        """Open the shutter.
        """
        self.log.debug(f"Received command 'openShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.OPEN
        # Both positions are expressed in percentage.
        self.position_actual = 100.0
        self.position_commanded = 100.0

    async def closeShutter(self):
        """Close the shutter.
        """
        self.log.debug(f"Received command 'closeShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.CLOSED
        # Both positions are expressed in percentage.
        self.position_actual = 0.0
        self.position_commanded = 0.0

    async def stopShutter(self):
        """Stop all motion of the shutter.
        """
        self.log.debug(f"Received command 'stopShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.STOPPED

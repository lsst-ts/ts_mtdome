import logging
import math
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
        self.position_error = 0.0
        self.position_actual = 0.0
        self.position_cmd = 0.0
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_error = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_cmd = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temp_actual = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.resolver_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.resolver_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
        self.power_absortion = 0.0

    async def determine_status(self, current_tai):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        time_diff = current_tai - self.command_time_tai
        self.log.debug(
            f"current_tai = {current_tai}, self.command_time_tai = {self.command_time_tai}, "
            f"time_diff = {time_diff}"
        )
        self.llc_status = {
            "status": self.status.value,
            "positionError": self.position_error,
            "positionActual": self.position_actual,
            "positionCmd": self.position_cmd,
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueError": self.drive_torque_error.tolist(),
            "driveTorqueCmd": self.drive_torque_cmd.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTempActual": self.drive_temp_actual.tolist(),
            "resolverHeadRaw": self.resolver_head_raw.tolist(),
            "resolverHeadCalibrated": self.resolver_head_calibrated.tolist(),
            "powerAbsortion": self.power_absortion,
        }
        self.log.debug(f"apcs_state = {self.llc_status}")

    async def openShutter(self):
        """Open the shutter.
        """
        self.log.info(f"Received command 'openShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.OPEN
        self.position_actual = math.radians(90.0)
        self.position_cmd = math.radians(90.0)

    async def closeShutter(self):
        """Close the shutter.
        """
        self.log.info(f"Received command 'closeShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.CLOSED
        self.position_actual = 0.0
        self.position_cmd = 0.0

    async def stopShutter(self):
        """Stop all motion of the shutter.
        """
        self.log.info(f"Received command 'stopShutter'")
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.STOPPED

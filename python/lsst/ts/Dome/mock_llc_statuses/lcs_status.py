__all__ = ["LlcStatus"]

import logging
import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from ..llc_status import LlcStatus

_NUM_LOUVERS = 34
_NUM_MOTORS = 68


class LcsStatus(BaseMockStatus):
    """Represents the status of the Louvers Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockLcsStatus")
        # variables holding the status of the mock Louvres
        self.status = np.full(_NUM_LOUVERS, LlcStatus.CLOSED.value, dtype=object)
        self.position_actual = np.zeros(_NUM_LOUVERS, dtype=float)
        self.position_commanded = np.zeros(_NUM_LOUVERS, dtype=float)
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_commanded = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temperature = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
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
                "status": self.status.tolist(),
                "positionActual": self.position_actual.tolist(),
                "positionCommanded": self.position_commanded.tolist(),
                "driveTorqueActual": self.drive_torque_actual.tolist(),
                "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
                "driveCurrentActual": self.drive_current_actual.tolist(),
                "driveTemperature": self.drive_temperature.tolist(),
                "encoderHeadRaw": self.encoder_head_raw.tolist(),
                "encoderHeadCalibrated": self.encoder_head_calibrated.tolist(),
                "powerDraw": self.power_draw,
                "timestamp": current_tai,
            }
        ]
        self.log.debug(f"lcs_state = {self.llc_status}")

    async def setLouvers(self, position):
        """Set the position of the louver with the given louver_id.

        Parameters
        ----------
        position: array of float
            An array with the positions (deg) to set the louvers to. 0 means closed, 180 means wide open,
            -1 means do not move. These limits are not checked.
        """
        self.command_time_tai = salobj.current_tai()
        for louver_id, pos in enumerate(position):
            if pos >= 0:
                if pos > 0:
                    self.status[louver_id] = LlcStatus.OPEN.value
                else:
                    self.status[louver_id] = LlcStatus.CLOSED.value
                self.position_actual[louver_id] = pos
                self.position_commanded[louver_id] = pos

    async def closeLouvers(self):
        """Close all louvers.
        """
        self.command_time_tai = salobj.current_tai()
        self.status[:] = LlcStatus.CLOSED.value
        self.position_actual[:] = 0.0
        self.position_commanded[:] = 0.0

    async def stopLouvers(self):
        """Stop all motion of all louvers.
        """
        self.command_time_tai = salobj.current_tai()
        self.status[:] = LlcStatus.STOPPED.value

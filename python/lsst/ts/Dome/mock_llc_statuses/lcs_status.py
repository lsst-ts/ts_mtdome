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
        self.position_error = np.zeros(_NUM_LOUVERS, dtype=float)
        self.position_actual = np.zeros(_NUM_LOUVERS, dtype=float)
        self.position_cmd = np.zeros(_NUM_LOUVERS, dtype=float)
        self.drive_torque_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_error = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_torque_cmd = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_current_actual = np.zeros(_NUM_MOTORS, dtype=float)
        self.drive_temp_actual = np.full(_NUM_MOTORS, 20.0, dtype=float)
        self.encoder_head_raw = np.zeros(_NUM_MOTORS, dtype=float)
        self.encoder_head_calibrated = np.zeros(_NUM_MOTORS, dtype=float)
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
            "status": self.status.tolist(),
            "positionError": self.position_error.tolist(),
            "positionActual": self.position_actual.tolist(),
            "positionCmd": self.position_cmd.tolist(),
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueError": self.drive_torque_error.tolist(),
            "driveTorqueCmd": self.drive_torque_cmd.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTempActual": self.drive_temp_actual.tolist(),
            "encoderHeadRaw": self.encoder_head_raw.tolist(),
            "encoderHeadCalibrated": self.encoder_head_calibrated.tolist(),
            "powerAbsortion": self.power_absortion,
        }
        self.log.debug(f"lcs_state = {self.llc_status}")

    async def setLouver(self, louver_id, position):
        """Set the position of the louver with the given louver_id.

        Parameters
        ----------
        louver_id: `int`
            The ID of the louver to set the position for. A zero based ID is assumed.
        position: `float`
            The position (deg) to set the louver to. 0 means closed, 180 means wide open. These limits are
            not checked.
        """
        self.command_time_tai = salobj.current_tai()
        self.status[louver_id] = LlcStatus.OPEN.value
        self.position_actual[louver_id] = position
        self.position_cmd[louver_id] = position

    async def closeLouvers(self):
        """Close all louvers.
        """
        self.command_time_tai = salobj.current_tai()
        self.status[:] = LlcStatus.CLOSED.value
        self.position_actual[:] = 0.0
        self.position_cmd[:] = 0.0

    async def stopLouvers(self):
        """Stop all motion of all louvers.
        """
        self.command_time_tai = salobj.current_tai()
        self.status[:] = LlcStatus.STOPPED.value

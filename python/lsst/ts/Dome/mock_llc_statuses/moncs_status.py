__all__ = ["MoncsStatus"]

import logging
import numpy as np

from .base_mock_status import BaseMockStatus
from ..llc_status import LlcStatus

_NUM_SENSORS = 16


class MoncsStatus(BaseMockStatus):
    """Represents the status of the Monitor Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockMoncsStatus")
        # variables holding the status of the mock Louvres
        self.status = LlcStatus.DISABLED
        self.data = np.zeros(_NUM_SENSORS, dtype=float)

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
            "data": self.data.tolist(),
        }
        self.log.debug(f"moncs_state = {self.llc_status}")

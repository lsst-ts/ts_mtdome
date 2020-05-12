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
        self.status = LlcStatus.DISABLED.value
        self.data = np.zeros(_NUM_SENSORS, dtype=float)

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        self.llc_status = {
            "status": self.status,
            "data": self.data.tolist(),
        }
        self.log.debug(f"moncs_state = {self.llc_status}")

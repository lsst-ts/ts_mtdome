import logging
import numpy as np

from .base_mock_status import BaseMockStatus
from ..llc_status import LlcStatus

NUM_SENSORS = 16


class ThcsStatus(BaseMockStatus):
    """Represents the status of the Thermal Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockThcsStatus")
        # variables holding the status of the mock Louvres
        self.status = LlcStatus.DISABLED.value
        self.data = np.zeros(NUM_SENSORS, dtype=float)

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        self.llc_status = {
            "status": self.status,
            "data": self.data.tolist(),
        }
        self.log.debug(f"thcs_state = {self.llc_status}")

    async def setTemperature(self, temperature):
        """Mock setting the preferred temperature in the dome. It should mock cooling down or warming up
        but it doesn't.

        Parameters
        ----------
        temperature: `float`
            The preferred temperature (deg). In reality this should be a realistic temperature in the range
            of about -30 C to +40 C but the provided temperature is not checked against this range.
        """
        self.status = LlcStatus.ENABLED.value
        self.data[:] = temperature
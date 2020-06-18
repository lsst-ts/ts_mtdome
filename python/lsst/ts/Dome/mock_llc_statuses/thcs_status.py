__all__ = ["ThcsStatus"]

import logging
import numpy as np

from lsst.ts import salobj
from .base_mock_status import BaseMockStatus
from ..llc_status import LlcStatus

_NUM_SENSORS = 16


class ThcsStatus(BaseMockStatus):
    """Represents the status of the Thermal Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockThcsStatus")
        # variables holding the status of the mock Louvres
        self.status = LlcStatus.DISABLED
        self.temperature = np.zeros(_NUM_SENSORS, dtype=float)

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
                "temperature": self.temperature.tolist(),
                "timestamp": current_tai,
            }
        ]
        self.log.debug(f"thcs_state = {self.llc_status}")

    async def setTemperature(self, temperature):
        """Set the preferred temperature in the dome. It should mock cooling down or warming up
        but it doesn't.

        Parameters
        ----------
        temperature: `float`
            The preferred temperature (degrees Celsius). In reality this should be a realistic temperature in
            the range of about -30 C to +40 C but the provided temperature is not checked against this range.
        """
        self.command_time_tai = salobj.current_tai()
        self.status = LlcStatus.ENABLED
        self.temperature[:] = temperature

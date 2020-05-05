import logging

from .base_mock_status import BaseMockStatus


class MockMoncsStatus(BaseMockStatus):
    """Represents the status of the Monitor Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockMoncsStatus")
        # variables holding the status of the mock Louvres
        self.status = "Disabled"
        self.data = [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        self.llc_status = {
            "status": self.status,
            "data": self.data,
        }
        self.log.debug(f"moncs_state = {self.llc_status}")

from abc import ABC, abstractmethod


class BaseMockStatus(ABC):
    """Abstract base class for all mock status classes used by the mock controller when in simulator mode.
    """

    def __init__(self):
        # dict to hold the status of the Lower Level Component.
        self.llc_status = {}

    @abstractmethod
    async def determine_status(self):
        """Abstract method that determines the status of the Lower Level Component to be implemented by all
        concrete sub-classes.
        """
        pass

from abc import ABC, abstractmethod


class BaseMockStatus(ABC):
    """Abstract base class for all mock status classes used by the mock controller when in simulator mode.
    """

    def __init__(self):
        # dict to hold the status of the Lower Level Component.
        self.llc_status = {}
        # time of the last executed command, in TAI Unix seconds
        self.command_time_tai = 0

    @abstractmethod
    async def determine_status(self, current_tai):
        """Abstract method that determines the status of the Lower Level Component to be implemented by all
        concrete sub-classes.

        Parameters
        ----------
        current_tai: `float`
            The current Unix TAI time, in seconds
        """
        pass

# This file is part of ts_MTDome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["BaseMockStatus"]

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseMockStatus(ABC):
    """Abstract base class for all mock status classes used by the mock
    controller when in simulator mode.
    """

    def __init__(self) -> None:
        # dict to hold the status of the Lower Level Component.
        self.llc_status: Dict[str, Any] = {}
        # time of the last executed command, in TAI Unix seconds
        self.command_time_tai = 0

    @abstractmethod
    async def determine_status(self, current_tai: float) -> None:
        """Abstract method that determines the status of the Lower Level
        Component to be implemented by all concrete sub-classes.

        Parameters
        ----------
        current_tai: `float`
            The current Unix TAI time, in seconds
        """
        pass

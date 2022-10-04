# This file is part of ts_mtdome.
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

__all__ = [
    "InternalMotionState",
    "LlcName",
    "LlcNameDict",
    "OnOff",
    "ResponseCode",
    "ValidSimulationMode",
    "motion_state_translations",
]

import enum

from lsst.ts.idl.enums.MTDome import MotionState, SubSystemId


class InternalMotionState(enum.IntEnum):
    """Internal Motion states.

    These get translated into IDL MotionState instances by the CSC.
    """

    DISABLED = enum.auto()
    STATIONARY = enum.auto()


# Dict holding translations from motion states, that the lower level
# controllers can have, to MotionState.
motion_state_translations = {
    "DISABLED": MotionState.ERROR,
    "STATIONARY": MotionState.STOPPED_BRAKED,
}


class LlcName(str, enum.Enum):
    """LLC names."""

    AMCS = "AMCS"
    APSCS = "ApSCS"
    LCS = "LCS"
    LWSCS = "LWSCS"
    MONCS = "MonCS"
    THCS = "ThCS"


class OnOff(enum.Enum):
    """ON or OFF."""

    ON = True
    OFF = False


class ResponseCode(enum.IntEnum):
    """Response codes."""

    OK = 0
    UNSUPPORTED_COMMAND = 2
    COMMAND_REJECTED = 3


class ValidSimulationMode(enum.IntEnum):
    """Valid values for the simulation_mode attribute of the CSC."""

    NORMAL_OPERATIONS = 0
    SIMULATION_WITH_MOCK_CONTROLLER = 1
    SIMULATION_WITHOUT_MOCK_CONTROLLER = 2


# Dictionary to look up which LlcName is associated with which sub-system.
LlcNameDict = {getattr(SubSystemId, enum.name): enum.value for enum in LlcName}

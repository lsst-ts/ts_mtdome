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
    "POSITION_TOLERANCE",
    "ZERO_VELOCITY_TOLERANCE",
    "InternalMotionState",
    "LlcName",
    "LlcNameDict",
    "MaxValueConfigType",
    "MaxValuesConfigType",
    "OnOff",
    "PowerManagementMode",
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

    STATIONARY = enum.auto()


# Dict holding translations from motion states, that the lower level
# controllers can have, to MotionState.
motion_state_translations = {
    "STATIONARY": MotionState.STOPPED_BRAKED,
}


class LlcName(str, enum.Enum):
    """LLC names."""

    AMCS = "AMCS"
    APSCS = "ApSCS"
    LCS = "LCS"
    LWSCS = "LWSCS"
    MONCS = "MonCS"
    RAD = "RAD"
    THCS = "ThCS"


class OnOff(enum.Enum):
    """ON or OFF."""

    ON = True
    OFF = False


class ResponseCode(enum.IntEnum):
    """Response codes.

    The codes mean

        * 0, "OK", "Command received correctly and is being executed."
        * 1, Not used.
        * 2, "Unsupported command", "A command was sent that is not supported
          by the lower level component, for instance park is sent to LCS or
          'mooveAz' instead of 'moveAz' to AMCS."
        * 3, "Incorrect parameter(s)", "The command that was sent is supported
          by the lower level component but the parameters for the command are
          incorrect. This can mean not enough parameters, too many parameters
          or one or more parameters with the wrong name."
        * 4, "Incorrect source", "The current command source is not valid, e.g.
          a remote command arrives while the system is operated in local mode,
          like the push buttons for the Aperture Shutters."
        * 5, "Incorrect state", "The current command cannot be executed in
          current state, e.g. moveAz when the AMCS is in fault state."
    """

    OK = 0
    UNSUPPORTED_COMMAND = 2
    INCORRECT_PARAMETERS = 3
    INCORRECT_SOURCE = 4
    INCORRECT_STATE = 5


class ValidSimulationMode(enum.IntEnum):
    """Valid values for the simulation_mode attribute of the CSC."""

    NORMAL_OPERATIONS = 0
    SIMULATION_WITH_MOCK_CONTROLLER = 1
    SIMULATION_WITHOUT_MOCK_CONTROLLER = 2


class PowerManagementMode(enum.Enum):
    """Power management modes for the CSC."""

    NO_POWER_MANAGEMENT = enum.auto()
    CONSERVATIVE_OPERATIONS = enum.auto()
    EMERGENCY = enum.auto()
    MAINTENANCE = enum.auto()


# Dictionary to look up which LlcName is associated with which sub-system.
LlcNameDict = {getattr(SubSystemId, enum.name): enum.value for enum in LlcName}

# Custom types used for configurable maximum values.
MaxValueConfigType = dict[str, str | list[float]]
MaxValuesConfigType = list[MaxValueConfigType]

# Tolerances for the azimuth motion. The position tolerance is from LTS-97.
ZERO_VELOCITY_TOLERANCE = 1e-7  # deg /sec
POSITION_TOLERANCE = 0.25  # deg

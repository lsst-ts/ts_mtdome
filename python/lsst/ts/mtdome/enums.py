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
    "LlcMotionState",
    "LlcName",
    "OnOff",
    "ResponseCode",
    "LlcNameDict",
]

import enum

from lsst.ts.idl.enums.MTDome import SubSystemId


class LlcMotionState(enum.IntEnum):
    """Motion states."""

    FAULT = 0
    CLOSED = 1
    CRAWLING = 2
    MOVING = 3
    OPEN = 4
    PARKED = 5
    PARKING = 6
    STOPPED = 7
    STOPPING = 8
    # Used by the lower level components and need to be translated to
    # IDL MotionState values.
    GO_STATIONARY = 9
    STATIONARY = 10
    ERROR = 11
    INFLATING = 12
    INFLATED = 13
    DEFLATING = 14
    DEFLATED = 15
    STARTING_MOTOR_COOLING = 16
    MOTOR_COOLING_ON = 17
    ENABLING_MOTOR_POWER = 18
    MOTOR_POWER_ON = 19
    GO_NORMAL = 20
    GO_DEGRADED = 21
    DISENGAGING_BRAKES = 22
    BRAKES_DISENGAGDED = 23
    ENGAGING_BRAKES = 24
    BRAKES_ENGAGDED = 25
    DISABLING_MOTOR_POWER = 26
    MOTOR_POWER_OFF = 27
    STOPPING_MOTOR_COOLING = 28
    MOTOR_COOLING_OFF = 29
    LP_ENGAGING = 30
    LP_ENGAGED = 31
    LP_DISENGAGING = 32
    LP_DISENGAGED = 33


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
    INCORRECT_PARAMETER = 3


# Dictionary to look up which LlcName is associated with which sub-system.
LlcNameDict = {getattr(SubSystemId, enum.name): enum.value for enum in LlcName}

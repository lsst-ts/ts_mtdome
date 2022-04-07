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
    "IntermediateState",
    "LlcMotionState",
    "LlcName",
    "OnOff",
    "ResponseCode",
    "LlcNameDict",
]

import enum

from lsst.ts.idl.enums.MTDome import SubSystemId


class IntermediateState(enum.IntEnum):
    BRAKES_DISENGAGED = enum.auto()
    BRAKES_ENGAGED = enum.auto()
    DEFLATED = enum.auto()
    DEFLATING = enum.auto()
    DISABLING_MOTOR_POWER = enum.auto()
    DISENGAGING_BRAKES = enum.auto()
    ENABLING_MOTOR_POWER = enum.auto()
    ENGAGING_BRAKES = enum.auto()
    GO_DEGRADED = enum.auto()
    GO_NORMAL = enum.auto()
    GO_STATIONARY = enum.auto()
    INFLATED = enum.auto()
    INFLATING = enum.auto()
    LP_DISENGAGED = enum.auto()
    LP_DISENGAGING = enum.auto()
    LP_ENGAGED = enum.auto()
    LP_ENGAGING = enum.auto()
    MOTOR_COOLING_OFF = enum.auto()
    MOTOR_COOLING_ON = enum.auto()
    MOTOR_POWER_OFF = enum.auto()
    MOTOR_POWER_ON = enum.auto()
    STARTING_MOTOR_COOLING = enum.auto()
    STOPPING_MOTOR_COOLING = enum.auto()


class LlcMotionState(enum.IntEnum):
    """Motion states."""

    CLOSED = enum.auto()
    CRAWLING = enum.auto()
    ERROR = enum.auto()
    MOVING = enum.auto()
    OPEN = enum.auto()
    PARKED = enum.auto()
    STATIONARY = enum.auto()
    STOPPED = enum.auto()


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


# Dictionary to look up which LlcName is associated with which sub-system.
LlcNameDict = {getattr(SubSystemId, enum.name): enum.value for enum in LlcName}

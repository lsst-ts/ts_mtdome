# This file is part of ts_mtdome.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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
    "POWER_MANAGEMENT_COMMANDS",
    "POSITION_TOLERANCE",
    "STOP_EL",
    "STOP_FANS",
    "STOP_LOUVERS",
    "STOP_SHUTTER",
    "UNCONTROLLED_LLCS",
    "ZERO_VELOCITY_TOLERANCE",
    "CommandName",
    "InternalMotionState",
    "LlcName",
    "LlcNameDict",
    "MaxValueConfigType",
    "MaxValuesConfigType",
    "ResponseCode",
    "ScheduledCommand",
    "SlipRingState",
    "StopCommand",
    "ValidSimulationMode",
    "motion_state_translations",
]

import enum
import typing
from dataclasses import dataclass

from lsst.ts.xml.enums.MTDome import MotionState, OnOff, SubSystemId


class InternalMotionState(enum.IntEnum):
    """Internal Motion states.

    These get translated into IDL MotionState instances by the CSC.
    """

    STATIONARY = enum.auto()


# Dict holding translations from motion states, that the lower level
# controllers can have, to MotionState.
motion_state_translations = {
    InternalMotionState.STATIONARY.name: MotionState.STOPPED_BRAKED,
}


class CommandName(enum.StrEnum):
    """Command names."""

    CLOSE_LOUVERS = "closeLouvers"
    CLOSE_SHUTTER = "closeShutter"
    CONFIG = "config"
    CRAWL_AZ = "crawlAz"
    CRAWL_EL = "crawlEl"
    EXIT_FAULT = "exitFault"
    FANS = "fans"
    GO_STATIONARY_AZ = "goStationaryAz"
    GO_STATIONARY_EL = "goStationaryEl"
    GO_STATIONARY_LOUVERS = "goStationaryLouvers"
    GO_STATIONARY_SHUTTER = "goStationaryShutter"
    INFLATE = "inflate"
    MOVE_AZ = "moveAz"
    MOVE_EL = "moveEl"
    OPEN_SHUTTER = "openShutter"
    PARK = "park"
    RESET_DRIVES_AZ = "resetDrivesAz"
    RESET_DRIVES_SHUTTER = "resetDrivesShutter"
    RESTORE = "restore"
    SEARCH_ZERO_SHUTTER = "searchZeroShutter"
    SET_DEGRADED_AZ = "setDegradedAz"
    SET_DEGRADED_EL = "setDegradedEl"
    SET_DEGRADED_LOUVERS = "setDegradedLouvers"
    SET_DEGRADED_SHUTTER = "setDegradedShutter"
    SET_DEGRADED_MONITORING = "setDegradedMonitoring"
    SET_DEGRADED_THERMAL = "setDegradedThermal"
    SET_LOUVERS = "setLouvers"
    SET_NORMAL_AZ = "setNormalAz"
    SET_NORMAL_EL = "setNormalEl"
    SET_NORMAL_LOUVERS = "setNormalLouvers"
    SET_NORMAL_SHUTTER = "setNormalShutter"
    SET_NORMAL_MONITORING = "setNormalMonitoring"
    SET_NORMAL_THERMAL = "setNormalThermal"
    SET_POWER_MANAGEMENT_MODE = "setPowerManagementMode"
    SET_TEMPERATURE = "setTemperature"
    SET_ZERO_AZ = "setZeroAz"
    STATUS_AMCS = "statusAMCS"
    STATUS_APSCS = "statusApSCS"
    STATUS_CBCS = "statusCBCS"
    STATUS_CSCS = "statusCSCS"
    STATUS_LCS = "statusLCS"
    STATUS_LWSCS = "statusLWSCS"
    STATUS_MONCS = "statusMonCS"
    STATUS_RAD = "statusRAD"
    STATUS_THCS = "statusThCS"
    STOP_AZ = "stopAz"
    STOP_EL = "stopEl"
    STOP_LOUVERS = "stopLouvers"
    STOP_SHUTTER = "stopShutter"


class LlcName(enum.StrEnum):
    """LLC names."""

    AMCS = "AMCS"
    APSCS = "ApSCS"
    CBCS = "CBCS"
    CSCS = "CSCS"
    LCS = "LCS"
    LWSCS = "LWSCS"
    MONCS = "MonCS"
    OBC = "OBC"
    RAD = "RAD"
    THCS = "ThCS"


class ResponseCode(enum.IntEnum):
    """Response codes.

    The codes mean

        * 0, "OK", "Command received correctly and is being executed."
        * 1, Not used.
        * 2, "Unsupported", "A command was sent that is not supported by the
          lower level component, for instance park is sent to LCS or 'mooveAz'
          instead of 'moveAz' to AMCS."
        * 3, "Incorrect parameter(s)", "The command that was sent is supported
          by the lower level component but the parameters for the command are
          incorrect. This can mean not enough parameters, too many parameters
          or one or more parameters with the wrong name."
        * 4, "Incorrect source", "The current command source is not valid, e.g.
          a remote command arrives while the system is operated in local mode,
          like the push buttons for the Aperture Shutters."
        * 5, "Incorrect state", "The current command cannot be executed in
          current state, e.g. moveAz when the AMCS is in fault state."
        * 6, "Rotating part did not receive", "It was not possible to forward
          the command to the rotating part."
        * 7, "Rotating part did not reply", "The command was sent to the
          rotating part, but it did not send a reply before a timeout."
    """

    OK = 0
    UNSUPPORTED = 2
    INCORRECT_PARAMETERS = 3
    INCORRECT_SOURCE = 4
    INCORRECT_STATE = 5
    ROTATING_PART_NOT_RECEIVED = 6
    ROTATING_PART_NOT_REPLIED = 7


class SlipRingState(enum.IntEnum):
    BELOW_LOW_LIMIT = enum.auto()
    OVER_LOW_LIMIT = enum.auto()
    COOLING_DOWN = enum.auto()


class ValidSimulationMode(enum.IntEnum):
    """Valid values for the simulation_mode attribute of the CSC."""

    NORMAL_OPERATIONS = 0
    SIMULATION_WITH_MOCK_CONTROLLER = 1
    SIMULATION_WITHOUT_MOCK_CONTROLLER = 2


# Dictionary to look up which LlcName is associated with which sub-system.
# TODO DM-44946 Remove the if but leave the rest as soon as XML 22.0 is
#  released.
LlcNameDict = {
    getattr(SubSystemId, enum.name): enum.value
    for enum in LlcName
    if hasattr(SubSystemId, enum.name)
}

# Custom types used for configurable maximum values.
MaxValueConfigType = dict[str, str | list[float]]
MaxValuesConfigType = list[MaxValueConfigType]

# Commands under power management.
POWER_MANAGEMENT_COMMANDS = [
    CommandName.CLOSE_LOUVERS,
    CommandName.CLOSE_SHUTTER,
    CommandName.CRAWL_EL,
    CommandName.FANS,
    CommandName.MOVE_EL,
    CommandName.OPEN_SHUTTER,
    CommandName.SEARCH_ZERO_SHUTTER,
    CommandName.SET_LOUVERS,
]

# Tolerances for the azimuth motion. The position tolerance is from LTS-97.
POSITION_TOLERANCE = 0.25  # deg
ZERO_VELOCITY_TOLERANCE = 1e-7  # deg /sec


@dataclass(order=True)
class ScheduledCommand:
    """Class representing a scheduled command.

    A command needs to be scheduled in case the power draw by it would cause
    the total power draw on the rotating part of the dome to exceed the
    threshold value defined in `CONTINUOUS_SLIP_RING_POWER_CAPACITY`.

    Parameters
    ----------
    command : `CommandName`
        The command that may need to be scheduled.
    params : `dict`[`str`, `typing.Any`]
        The parameters for the command. Defaults to None.
    """

    command: CommandName
    params: dict[str, typing.Any]


@dataclass
class StopCommand:
    """Class representing a command to stop an ongoing motion.

    An ongoing motion may need to be stopped if the subsystem, represented by
    the LlcName, draws power so that issuing a higher priority command would
    push the power draw over the slip ring limit.

    Parameters
    ----------
    scheduled_command : `ScheduledCommand`
        The command and its parameters that will stop the ongoing motion.
    llc_name : `LlcName`
        The name of the subsystem, or Lower Level Component, that the stop
        command is issued for. This name is used to check if the subsystem
        currently draws power so that issuing a higher priority command would
        push the power draw over the slip ring limit.
    """

    scheduled_command: ScheduledCommand
    llc_name: LlcName


# Stop commands.
STOP_EL = StopCommand(
    ScheduledCommand(command=CommandName.STOP_EL, params={}),
    LlcName.LWSCS,
)
STOP_FANS = StopCommand(
    ScheduledCommand(command=CommandName.FANS, params={"action": OnOff.OFF}),
    LlcName.AMCS,
)
STOP_LOUVERS = StopCommand(
    ScheduledCommand(command=CommandName.STOP_LOUVERS, params={}),
    LlcName.LCS,
)
STOP_SHUTTER = StopCommand(
    ScheduledCommand(command=CommandName.STOP_SHUTTER, params={}),
    LlcName.APSCS,
)

# These LLCs are not cointrolled by the cRIO.
UNCONTROLLED_LLCS = [LlcName.RAD, LlcName.CSCS, LlcName.OBC]

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

__all__ = ["MTDomeCsc", "DOME_AZIMUTH_OFFSET", "CommandTime", "run_mtdome"]

import asyncio
import math
import typing
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
from lsst.ts import salobj, tcpip, utils
from lsst.ts.idl.enums.MTDome import (
    EnabledState,
    MotionState,
    OperationalMode,
    SubSystemId,
)

from . import __version__
from .config_schema import CONFIG_SCHEMA
from .csc_utils import support_command
from .enums import (
    POSITION_TOLERANCE,
    ZERO_VELOCITY_TOLERANCE,
    LlcName,
    LlcNameDict,
    MaxValueConfigType,
    MaxValuesConfigType,
    ResponseCode,
    ValidSimulationMode,
    motion_state_translations,
)
from .llc_configuration_limits import AmcsLimits, LwscsLimits
from .mock_controller import MockMTDomeController

# Timeout [sec] used when creating a Client, a mock controller or when waiting
# for a reply when sending a command to the controller.
_TIMEOUT = 20

_KEYS_TO_REMOVE = {
    "status",
    "operationalMode",  # Remove because gets emitted as an event
    "appliedConfiguration",  # Remove because gets emitted as an event
}

# The values of these keys need to be compensated for the dome azimuth offset
# in the AMCS status. Note that these keys are shared with LWSCS so they can be
# added to _KEYS_IN_RADIANS to avoid duplication but this also means that an
# additional check for the AMCS lower level component needs to be done when
# applying the offset correction. That is a trade off I can live with.
_AMCS_KEYS_OFFSET = {
    "positionActual",
    "positionCommanded",
}
# The values of these keys need to be converted from radians to degrees when
# the status is recevied and telemetry with these values is sent.
_KEYS_IN_RADIANS = {
    "velocityActual",
    "velocityCommanded",
}.union(_AMCS_KEYS_OFFSET)
# The values of the following ApSCS keys are lists and also need to be
# converted from radians to degrees.
_APSCS_LIST_KEYS_IN_RADIANS = {"positionActual"}

# The offset of the dome rotation zero point with respect to azimuth 0º (true
# north) is 32º west and this needs to be added when commanding the azimuth
# position, or subtracted when sending the azimuth telemetry.
DOME_AZIMUTH_OFFSET = 32.0

# Polling periods [sec] for the lower level components.
_AMCS_STATUS_PERIOD = 0.2
_APSCS_STATUS_PERIOD = 2.0
_LCS_STATUS_PERIOD = 2.0
_LWSCS_STATUS_PERIOD = 2.0
_MONCS_STATUS_PERIOD = 2.0
_THCS_STATUS_PERIOD = 2.0

# Polling period [sec] for the task that checks if all commands have been
# replied to.
_COMMANDS_REPLIED_PERIOD = 600

# These next commands are temporarily disabled in simulation mode 0 because
# they will be issued during the upcoming TMA pointing test and the EIE LabVIEW
# code doesn't handle them yet, which will result in an error. As soon as the
# TMA pointing test is done, they will be reenabled. The name reflects the fact
# that there probably will be more situations during commissioning in which
# commands need to be disabled.
COMMANDS_DISABLED_FOR_COMMISSIONING = {
    "closeLouvers",
    "crawlEl",
    "fans",
    "goStationaryEl",
    "goStationaryLouvers",
    "inflate",
    "moveEl",
    "setLouvers",
    "setTemperature",
    "stopEl",
    "stopLouvers",
}
REPLY_DATA_FOR_DISABLED_COMMANDS = {"response": 0, "timeout": 0}

# All status methods and the intervals at which they are executed. The boolean
# indicates whther they are used for commissioning (True) or not. Note that all
# methods always are used for unit testing.
ALL_METHODS_AND_INTERVALS = {
    "statusAMCS": (_AMCS_STATUS_PERIOD, True),
    "statusApSCS": (_APSCS_STATUS_PERIOD, False),
    "statusLCS": (_LCS_STATUS_PERIOD, False),
    "statusLWSCS": (_LWSCS_STATUS_PERIOD, False),
    "statusMonCS": (_MONCS_STATUS_PERIOD, False),
    "statusThCS": (_THCS_STATUS_PERIOD, False),
    "check_all_commands_have_replies": (_COMMANDS_REPLIED_PERIOD, True),
}

ALL_OPERATIONAL_MODE_COMMANDS = {
    SubSystemId.AMCS: {
        OperationalMode.NORMAL.name: "setNormalAz",
        OperationalMode.DEGRADED.name: "setDegradedAz",
    },
    SubSystemId.LWSCS: {
        OperationalMode.NORMAL.name: "setNormalEl",
        OperationalMode.DEGRADED.name: "setDegradedEl",
    },
    SubSystemId.APSCS: {
        OperationalMode.NORMAL.name: "setNormalShutter",
        OperationalMode.DEGRADED.name: "setDegradedShutter",
    },
    SubSystemId.LCS: {
        OperationalMode.NORMAL.name: "setNormalLouvers",
        OperationalMode.DEGRADED.name: "setDegradedLouvers",
    },
    SubSystemId.MONCS: {
        OperationalMode.NORMAL.name: "setNormalMonitoring",
        OperationalMode.DEGRADED.name: "setDegradedMonitoring",
    },
    SubSystemId.THCS: {
        OperationalMode.NORMAL.name: "setNormalThermal",
        OperationalMode.DEGRADED.name: "setDegradedThermal",
    },
}

OPERATIONAL_MODE_COMMANDS_FOR_COMMISSIONING = {
    SubSystemId.AMCS: {
        OperationalMode.NORMAL.name: "setNormalAz",
        OperationalMode.DEGRADED.name: "setDegradedAz",
    },
}


def run_mtdome() -> None:
    asyncio.run(MTDomeCsc.amain(index=None))


@dataclass
class MoveAzCommandData:
    """Class representing the data for a moveAz command.

    Attributes
    ----------
    position : `float`
        The position to move to [deg].
    velocity : `float`
        The velocity at which the target position is moving [deg/sec].
    """

    position: float = math.nan
    velocity: float = math.nan


@dataclass
class CommandTime:
    """Class representing the TAI time at which a command was issued.

    Attributes
    ----------
    command : `str`
        The command issued.
    tai : `float`
        TAI time as unix seconds, e.g. the time returned by CLOCK_TAI
        on linux systems.
    """

    command: str
    tai: float


class MTDomeCsc(salobj.ConfigurableCsc):
    """Upper level Commandable SAL Component to interface with the Simonyi
    Survey Telescope Dome lower level components.

    Parameters
    ----------
    config_dir : `string`
        The configuration directory
    initial_state : `salobj.State`
        The initial state of the CSC
    simulation_mode : `int`
        Simulation mode.
    override : `str`, optional
        Override of settings if ``initial_state`` is `State.DISABLED`
        or `State.ENABLED`.

    Notes
    -----
    **Simulation Modes**

    Supported simulation modes:

    * 0: regular operation
    * 1: simulation mode: start a mock TCP/IP MTDome controller and talk to it
    * 2: simulation mode: talk to a running TCP/IP MTDome controller

    In simulation mode 0, the site specific configuration will be sent to the
    MTDome controller. In both simulation modes 1 and 2, a configuration with
    mock devices will be sent to the MTDome controller. This allows for testing
    and/or debugging the MTDome CSC.
    """

    _index_iter = utils.index_generator()
    enable_cmdline_state = True
    valid_simulation_modes = set([v.value for v in ValidSimulationMode])
    version = __version__

    def __init__(
        self,
        config_dir: typing.Optional[str] = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = ValidSimulationMode.NORMAL_OPERATIONS,
        override: str = "",
    ) -> None:
        self.client: tcpip.Client | None = None
        self.config: typing.Optional[SimpleNamespace] = None

        self.mock_ctrl: typing.Optional[
            MockMTDomeController
        ] = None  # mock controller, or None if not constructed

        # Check supported commands to make sure of backward compatibility with
        # XML 12.0.
        if support_command("resetDrivesShutter"):
            setattr(self, "do_resetDrivesShutter", self._do_resetDrivesShutter)
        if support_command("home"):
            setattr(self, "do_home", self._do_home)

        super().__init__(
            name="MTDome",
            index=0,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
            override=override,
        )

        # Keep the lower level statuses in memory for unit tests.
        self.lower_level_status: dict[str, typing.Any] = {}
        # List of periodic tasks to start.
        self.periodic_tasks: list[asyncio.Future] = []
        # Keep track of the AMCS state for logging one the console.
        self.amcs_state: MotionState | None = None
        # Keep track of the AMCS status message for logging on the console.
        self.amcs_message: str = ""

        # Keep a lock so only one remote command can be executed at a time.
        self.communication_lock = asyncio.Lock()

        self.amcs_limits = AmcsLimits()
        self.lwscs_limits = LwscsLimits()

        # Keep track of which stop function to call for which SubSystemId
        self.stop_function_dict = {
            SubSystemId.AMCS: self.stop_az,
            SubSystemId.LWSCS: self.stop_el,
            SubSystemId.APSCS: self.stop_shutter,
            SubSystemId.LCS: self.stop_louvers,
        }

        # Keep track of which command to send to set the operational mode on a
        # lower level component.
        self.operational_mode_command_dict = ALL_OPERATIONAL_MODE_COMMANDS
        if self.simulation_mode == ValidSimulationMode.NORMAL_OPERATIONS:
            self.operational_mode_command_dict = (
                OPERATIONAL_MODE_COMMANDS_FOR_COMMISSIONING
            )

        # Keep track of which command to send the home command on a lower level
        # component.
        self.set_home_command_dict = {
            SubSystemId.APSCS: "searchZeroShutter",
        }

        # TODO DM-37170: Remove as soon as the IDLE state is not used anymore
        #  by the AMCS.
        self.previous_state = MotionState.PARKED

        # Keep track of the parameters of the current moveAz command issued so
        # repetition of the same command can be avoided. This is necessary in
        # case the dome repeatedly is instructed to move to the same position
        # with velocity == 0.0 since that may introduce large oscillations.
        self.current_moveAz_command = MoveAzCommandData()

        # Keep track of the commands that have been sent and that haven't been
        # replied to yet. The key of the dict is the commandId for the commands
        # that have been sent.
        self.commands_without_reply: dict[int, CommandTime] = {}

        self.log.info("DomeCsc constructed.")

    async def connect(self) -> None:
        """Connect to the dome controller's TCP/IP port.

        Start the mock controller, if simulating.
        """
        self.log.info("connect")
        self.log.info(self.config)
        self.log.info(f"self.simulation_mode = {self.simulation_mode}.")
        if self.config is None:
            raise RuntimeError("Not yet configured.")
        if self.connected:
            raise RuntimeError("Already connected.")
        if self.simulation_mode == ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER:
            await self.start_mock_ctrl()
            assert self.mock_ctrl is not None
            host = self.mock_ctrl.host
            port = self.mock_ctrl.port
        elif (
            self.simulation_mode
            == ValidSimulationMode.SIMULATION_WITHOUT_MOCK_CONTROLLER
        ):
            host = tcpip.DEFAULT_LOCALHOST
            port = self.config.port
        else:
            host = self.config.host
            port = self.config.port
        try:
            self.log.info(f"Connecting to host={host} and port={port}.")
            self.client = tcpip.Client(
                host=host, port=port, log=self.log, name="MTDomeClient"
            )
            await asyncio.wait_for(fut=self.client.start_task, timeout=_TIMEOUT)
        except ConnectionError as e:
            await self.fault(code=3, report=f"Connection to server failed: {e}.")
            raise

        # DM-26374: Send enabled events for az and el since they are always
        # enabled.
        # DM-35794: Also send enabled event for Aperture Shutter.
        await self.evt_azEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        await self.evt_elEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        # Check supported event to make sure of backward compatibility with
        # XML 12.0.
        if hasattr(self, "evt_shutterEnabled"):
            await self.evt_shutterEnabled.set_write(
                state=EnabledState.ENABLED, faultCode=""
            )

        # DM-26374: Send events for the brakes, interlocks and locking pins
        # with a default value of 0 (meaning nothing engaged) until the
        # corresponding enums have been defined. This will be done in
        # DM-26863.
        await self.evt_brakesEngaged.set_write(brakes=0)
        await self.evt_interlocks.set_write(interlocks=0)
        await self.evt_lockingPinsEngaged.set_write(engaged=0)

        # Start polling for the status of the lower level components
        # periodically.
        await self.start_periodic_tasks()

        self.log.info("connected")

    async def _set_maximum_motion_values(self) -> None:
        assert self.config is not None
        vmax = self.config.amcs_vmax
        amax = self.config.amcs_amax
        jmax = self.config.amcs_jmax
        self.log.info(f"Setting AMCS maximum velocity to {vmax}.")
        vmax_dict: MaxValueConfigType = {"target": "vmax", "setting": [vmax]}
        self.log.info(f"Setting AMCS maximum acceleration to {amax}.")
        amax_dict: MaxValueConfigType = {"target": "amax", "setting": [amax]}
        self.log.info(f"Setting AMCS maximum jerk to {jmax}.")
        jmax_dict: MaxValueConfigType = {"target": "jmax", "setting": [jmax]}
        settings = [vmax_dict, amax_dict, jmax_dict]
        await self.config_llcs(system=LlcName.AMCS, settings=settings)

    async def cancel_periodic_tasks(self) -> None:
        """Cancel all periodic tasks."""
        while self.periodic_tasks:
            self.periodic_tasks.pop().cancel()

    async def start_periodic_tasks(self) -> None:
        """Start all periodic tasks."""
        await self.cancel_periodic_tasks()
        for method, interval_and_execute in ALL_METHODS_AND_INTERVALS.items():
            interval, execute = interval_and_execute
            if (
                self.simulation_mode == ValidSimulationMode.NORMAL_OPERATIONS
                and execute is False
            ):
                continue
            func = getattr(self, method)
            self.periodic_tasks.append(
                asyncio.create_task(self.one_periodic_task(func, interval))
            )

    async def one_periodic_task(self, method: typing.Callable, interval: float) -> None:
        """Run one method forever at the specified interval.

        Parameters
        ----------
        method: coro
            The periodic method to run.
        interval: `float`
            The interval (sec) at which to run the status method.

        """
        try:
            while True:
                await method()
                await asyncio.sleep(interval)
        except Exception as e:
            self.log.exception(
                f"one_periodic_task({method}) failed because of {e!r}. The task has stopped."
            )

    async def disconnect(self) -> None:
        """Disconnect from the TCP/IP controller, if connected, and stop the
        mock controller, if running.
        """
        self.log.info("disconnect.")

        # Stop all periodic tasks, including polling for the status of the
        # lower level components.
        await self.cancel_periodic_tasks()

        if self.connected:
            assert self.client is not None  # make mypy happy
            await self.client.close()
            self.client = None
        if self.simulation_mode == ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER:
            await self.stop_mock_ctrl()

    async def start_mock_ctrl(self) -> None:
        """Start the mock controller.

        The simulation mode must be 1.
        """
        self.log.info("start_mock_ctrl.")
        try:
            assert (
                self.simulation_mode
                == ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER.value
            )
            self.mock_ctrl = MockMTDomeController(port=0, log=self.log)
            await asyncio.wait_for(self.mock_ctrl.start(), timeout=_TIMEOUT)

        except Exception as e:
            await self.fault(code=3, report=f"Could not start mock controller: {e}")
            raise

    async def stop_mock_ctrl(self) -> None:
        """Stop the mock controller, if running."""
        self.log.info("stop_mock_ctrl")
        mock_ctrl = self.mock_ctrl
        self.mock_ctrl = None
        if mock_ctrl:
            await mock_ctrl.close()

    async def handle_summary_state(self) -> None:
        """Override of the handle_summary_state function to connect or
        disconnect to the lower level components (or the mock_controller) when
        needed.
        """
        self.log.info(f"handle_summary_state {self.summary_state.name}")
        if self.disabled_or_enabled:
            if not self.connected:
                self.current_moveAz_command = MoveAzCommandData()
                await self.connect()
        else:
            await self.disconnect()

    async def end_enable(self, data: salobj.BaseDdsDataType) -> None:
        """End do_enable; called after state changes
        but before command acknowledged.

        Parameters
        ----------
        data : `salobj.BaseDdsDataType`
            Command data
        """
        await super().end_enable(data)

        if self.simulation_mode != ValidSimulationMode.NORMAL_OPERATIONS:
            # For backward compatibility with XML 12.0, we always send the
            # searchZeroShutter command.
            await self.write_then_read_reply(command="searchZeroShutter")

        assert self.config is not None
        if (
            self.config.amcs_vmax > 0
            and self.config.amcs_amax > 0
            and self.config.amcs_jmax > 0
        ):
            await self._set_maximum_motion_values()
        else:
            self.log.info("Not setting AMCS maximum velocity, acceleration and jerk.")

    async def write_then_read_reply(
        self, command: str, **params: typing.Any
    ) -> dict[str, typing.Any]:
        """Write the cmd string and then read the reply to the command.

        Parameters
        ----------
        command: `str`
            The command to write.
        **params:
            The parameters for the command. This may be empty.

        Returns
        -------
        data : `dict`
            A dict of the form {"response": ResponseCode, "timeout":
            TimeoutValue} where "response" can be zero for "OK" or non-zero
            for "ERROR".
        """
        command_id = next(self._index_iter)
        self.commands_without_reply[command_id] = CommandTime(
            command=command, tai=utils.current_tai()
        )
        command_dict = dict(commandId=command_id, command=command, parameters=params)
        async with self.communication_lock:
            if self.client is None:
                await self.fault(
                    code=3,
                    report=f"Error writing command {command_dict}: self.client == None.",
                )
                raise RuntimeError("self.client == None.")

            disabled_commands: set[str] = set()
            if self.simulation_mode == ValidSimulationMode.NORMAL_OPERATIONS:
                disabled_commands = COMMANDS_DISABLED_FOR_COMMISSIONING

            if command not in disabled_commands:
                try:
                    await self.client.write_json(data=command_dict)
                    data = await asyncio.wait_for(
                        self.client.read_json(), timeout=_TIMEOUT
                    )
                except Exception as e:
                    await self.fault(
                        code=3,
                        report=f"Error reading reply to command {command_dict}: {e}.",
                    )
                    raise
                received_command_id = data["commandId"]
                if received_command_id in self.commands_without_reply:
                    self.commands_without_reply.pop(received_command_id)
                else:
                    self.log.warning(
                        f"Ignoring unknown commandId {received_command_id}."
                    )
            else:
                data = REPLY_DATA_FOR_DISABLED_COMMANDS
            response = data["response"]

            if response != ResponseCode.OK:
                self.log.error(f"Received ERROR {data}.")
                error_suffix = {
                    ResponseCode.INCORRECT_PARAMETERS: "has incorrect parameters.",
                    ResponseCode.INCORRECT_SOURCE: "was sent from an incorrect source.",
                    ResponseCode.INCORRECT_STATE: "was sent for an incorrect state.",
                }.get(response, "is not supported.")
                raise ValueError(f"{command=} {error_suffix}")

            return data

    def is_moveAz_same_as_current(self, position: float, velocity: float) -> bool:
        """Is the received moveAz command the same as the current moveAz
        command or not.

        Parameters
        ----------
        position : `float`
            The target position to move to.
        velocity : `float`
            The velocity at which the target position is moving.

        Returns
        -------
        bool
            True if the issues moveAz command is the same as the current moveAz
            command or False otherwise.

        Notes
        -----
        The moveAz command is regarded to be the same as the current one if and
        only if the position is the same and the velocity is 0.0. In all other
        cases the command is regarded not to be the same. This is important
        because, if the velocity != 0.0, the dome is following a moving target
        and the chance of it being at exactly the commanded position with the
        commanded velocity can be considered zero and therefore the moveAz
        command has to be sent to the dome.

        The very first moveAz command, when connecting to the low-level
        controller, always is executed, even if the position matches the
        current position of the dome. The risk of causing vibrations in this
        case is so low that it doesn't warrant the hassle of reading the
        telemetry and determining if it is safe to execute the moveAz command.

        The tolerance for the position is 0.25 deg as specified in LTS-97. The
        tolerance for the velocity is set to a small but non-zero value. See
        `lsst.ts.mtdome.enums` for more information.
        """
        if (
            math.isclose(velocity, 0.0, abs_tol=ZERO_VELOCITY_TOLERANCE)
            and math.isclose(
                position,
                self.current_moveAz_command.position,
                abs_tol=POSITION_TOLERANCE,
            )
            and math.isclose(
                velocity,
                self.current_moveAz_command.velocity,
                abs_tol=ZERO_VELOCITY_TOLERANCE,
            )
        ):
            return True
        self.current_moveAz_command.position = position
        self.current_moveAz_command.velocity = velocity
        return False

    async def do_moveAz(self, data: SimpleNamespace) -> None:
        """Move AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"do_moveAz: {data.position=!s}, {data.velocity=!s}")
        # Compensate for the dome azimuth offset.
        position = utils.angle_wrap_nonnegative(
            data.position + DOME_AZIMUTH_OFFSET
        ).degree
        if not self.is_moveAz_same_as_current(
            position=data.position, velocity=data.velocity
        ):
            await self.write_then_read_reply(
                command="moveAz",
                position=math.radians(position),
                velocity=math.radians(data.velocity),
            )
            await self.evt_azTarget.set_write(
                position=data.position, velocity=data.velocity
            )

    async def do_moveEl(self, data: SimpleNamespace) -> None:
        """Move El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"do_moveEl: {data.position=!s}")
        await self.write_then_read_reply(
            command="moveEl", position=math.radians(data.position)
        )
        await self.evt_elTarget.set_write(position=data.position, velocity=0)

    async def stop_az(self, engage_brakes: bool) -> None:
        """Stop AZ motion and engage the brakes if indicated. Also
        disengage the locking pins if engaged.

        Parameters
        ----------
        engage_brakes : bool
            Engage the brakes (true) or not (false).
        """
        self.log.debug(f"stop_az: {engage_brakes=!s}")
        self.assert_enabled()
        if engage_brakes:
            await self.write_then_read_reply(command="goStationaryAz")
        else:
            await self.write_then_read_reply(command="stopAz")

    async def stop_el(self, engage_brakes: bool) -> None:
        """Stop EL motion and engage the brakes if indicated. Also
        disengage the locking pins if engaged.

        Parameters
        ----------
        engage_brakes : bool
            Engage the brakes (true) or not (false).
        """
        self.log.debug(f"stop_el: {engage_brakes=!s}")
        self.assert_enabled()
        if engage_brakes:
            await self.write_then_read_reply(command="goStationaryEl")
        else:
            await self.write_then_read_reply(command="stopEl")

    async def stop_louvers(self, engage_brakes: bool) -> None:
        """Stop Louvers motion and engage the brakes if indicated.
        Also disengage the locking pins if engaged.

        Parameters
        ----------
        engage_brakes : bool
            Engage the brakes (true) or not (false).
        """
        self.log.debug(f"stop_louvers: {engage_brakes=!s}")
        self.assert_enabled()
        if engage_brakes:
            await self.write_then_read_reply(command="goStationaryLouvers")
        else:
            await self.write_then_read_reply(command="stopLouvers")

    async def stop_shutter(self, engage_brakes: bool) -> None:
        """Stop Shutter motion and engage the brakes if indicated.
        Also disengage the locking pins if engaged.

        Parameters
        ----------
        engage_brakes : bool
            Engage the brakes (true) or not (false).
        """
        self.log.debug(f"stop_shutter: {engage_brakes=!s}")
        self.assert_enabled()
        if engage_brakes:
            await self.write_then_read_reply(command="goStationaryShutter")
        else:
            await self.write_then_read_reply(command="stopShutter")

    async def do_stop(self, data: SimpleNamespace) -> None:
        """Stop all motion and engage the brakes if indicated in the data.
        Also disengage the locking pins if engaged.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        for sub_system_id in SubSystemId:
            # Do not nest these two if statements, otherwise a warning will be
            # logged for each SubsystemId that is not in data.subSystemIds.
            if sub_system_id & data.subSystemIds:
                if sub_system_id in self.stop_function_dict:
                    func = self.stop_function_dict[sub_system_id]
                    await func(data.engageBrakes)
                else:
                    self.log.warning(
                        f"Subsystem {SubSystemId(sub_system_id).name} doesn't have a "
                        "stop function. Ignoring."
                    )

    async def do_crawlAz(self, data: SimpleNamespace) -> None:
        """Crawl AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_crawlAz: {data.velocity=!s}")
        self.assert_enabled()
        await self.write_then_read_reply(
            command="crawlAz", velocity=math.radians(data.velocity)
        )
        await self.evt_azTarget.set_write(position=float("nan"), velocity=data.velocity)

    async def do_crawlEl(self, data: SimpleNamespace) -> None:
        """Crawl El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_crawlEl: {data.velocity=!s}")
        self.assert_enabled()
        await self.write_then_read_reply(
            command="crawlEl", velocity=math.radians(data.velocity)
        )
        await self.evt_elTarget.set_write(position=float("nan"), velocity=data.velocity)

    async def do_setLouvers(self, data: SimpleNamespace) -> None:
        """Set Louver.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_setLouvers: {data.position=!s}")
        self.assert_enabled()
        await self.write_then_read_reply(command="setLouvers", position=data.position)

    async def do_closeLouvers(self, data: SimpleNamespace) -> None:
        """Close Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_closeLouvers")
        self.assert_enabled()
        await self.write_then_read_reply(command="closeLouvers")

    async def do_openShutter(self, data: SimpleNamespace) -> None:
        """Open Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_openShutter")
        self.assert_enabled()
        await self.write_then_read_reply(command="openShutter")

    async def do_closeShutter(self, data: SimpleNamespace) -> None:
        """Close Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_closeShutter")
        self.assert_enabled()
        await self.write_then_read_reply(command="closeShutter")

    async def do_park(self, data: SimpleNamespace) -> None:
        """Park, meaning stop all motion and engage the brakes and locking
        pins.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_park")
        self.assert_enabled()
        await self.write_then_read_reply(command="park")
        await self.evt_azTarget.set_write(
            position=360.0 - DOME_AZIMUTH_OFFSET, velocity=0
        )

    async def do_setTemperature(self, data: SimpleNamespace) -> None:
        """Set Temperature.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_setTemperature: {data.temperature=!s}")
        self.assert_enabled()
        await self.write_then_read_reply(
            command="setTemperature", temperature=data.temperature
        )

    async def do_exitFault(self, data: SimpleNamespace) -> None:
        """Indicate that all hardware errors, leading to fault state, have been
        resolved.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()

        # For backward compatibility with XML 12.0, we always send resetDrives
        # commands.
        az_reset = [1, 1, 1, 1, 1]
        self.log.debug(f"resetDrivesAz: {az_reset=!s}")
        await self.write_then_read_reply(command="resetDrivesAz", reset=az_reset)
        if self.simulation_mode != ValidSimulationMode.NORMAL_OPERATIONS:
            aps_reset = [1, 1, 1, 1]
            self.log.debug(f"resetDrivesShutter: {aps_reset=!s}")
            await self.write_then_read_reply(
                command="resetDrivesShutter", reset=aps_reset
            )
        self.log.debug("do_exitFault")
        await self.write_then_read_reply(command="exitFault")

    async def do_setOperationalMode(self, data: SimpleNamespace) -> None:
        """Indicate that one or more sub_systems need to operate in degraded
        (true) or normal (false) state.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        operational_mode = OperationalMode(data.operationalMode)
        sub_system_ids: int = data.subSystemIds
        for sub_system_id in SubSystemId:
            if (
                sub_system_id & sub_system_ids
                and sub_system_id in self.operational_mode_command_dict
                and operational_mode.name
                in self.operational_mode_command_dict[sub_system_id]
            ):
                self.log.debug(
                    f"do_setOperationalMode: sub_system_id={sub_system_id.name}"
                )
                command = self.operational_mode_command_dict[sub_system_id][
                    operational_mode.name
                ]
                await self.write_then_read_reply(command=command)
                await self.evt_operationalMode.set_write(
                    operationalMode=operational_mode,
                    subSystemId=sub_system_id,
                )

    async def do_resetDrivesAz(self, data: SimpleNamespace) -> None:
        """Reset one or more AZ drives. This is necessary when exiting from
        FAULT state without going to Degraded Mode since the drives don't reset
        themselves.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        reset_ints = [int(value) for value in data.reset]
        self.log.debug(f"do_resetDrivesAz: reset={reset_ints}")
        await self.write_then_read_reply(command="resetDrivesAz", reset=reset_ints)

    async def _do_resetDrivesShutter(self, data: SimpleNamespace) -> None:
        """Reset one or more Aperture Shutter drives. This is necessary when
        exiting from FAULT state without going to Degraded Mode since the
        drives don't reset themselves.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        reset_ints = [int(value) for value in data.reset]
        self.log.debug(f"do_resetDrivesShutter: reset={reset_ints}")
        await self.write_then_read_reply(command="resetDrivesShutter", reset=reset_ints)

    async def do_setZeroAz(self, data: SimpleNamespace) -> None:
        """Take the current position of the dome as zero. This is necessary as
        long as the racks and pinions on the drives have not been installed yet
        to compensate for slippage of the drives.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_setZeroAz")
        self.assert_enabled()
        await self.write_then_read_reply(command="calibrateAz")

    async def _do_home(self, data: SimpleNamespace) -> None:
        """Search the home position of the Aperture Shutter, which is the
        closed position.

        This is necessary in case the ApSCS (Aperture Shutter Control system)
        was shutdown with the Aperture Shutter not fully open or fully closed.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        sub_system_ids: int = data.subSystemIds
        for sub_system_id in SubSystemId:
            self.log.debug(f"do_home: sub_system_id={sub_system_id.name}")
            if (
                sub_system_id & sub_system_ids
                and sub_system_id in self.set_home_command_dict
            ):
                command = self.set_home_command_dict[sub_system_id]
                await self.write_then_read_reply(command=command)

    async def config_llcs(self, system: str, settings: MaxValuesConfigType) -> None:
        """Config command not to be executed by SAL.

        This command will be used to send the values of one or more parameters
        to configure the lower level components.

        Parameters
        ----------
        system: `str`
            The name of the lower level component to configure.
        settings : `dict`
            A dict containing key,value for all the parameters that need to be
            configured. The structure is::

                "jmax"
                "amax"
                "vmax"

        """
        self.log.debug("config_llcs")
        if system == LlcName.AMCS:
            converted_settings = self.amcs_limits.validate(settings)
        elif system == LlcName.LWSCS:
            converted_settings = self.lwscs_limits.validate(settings)
        else:
            raise ValueError(f"Encountered unsupported {system=!s}")

        await self.write_then_read_reply(
            command="config", system=system, settings=converted_settings
        )

    async def restore_llcs(self) -> None:
        await self.write_then_read_reply(command="restore")

    async def fans(self, data: dict[str, typing.Any]) -> None:
        """Fans command not to be executed by SAL.

        This command will be used to switch on or off the fans in the dome.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain
            the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply(command="fans", action=data["action"])

    async def inflate(self, data: dict[str, typing.Any]) -> None:
        """Inflate command not to be executed by SAL.

        This command will be used to inflate or deflate the inflatable seal.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain
            the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply(command="inflate", action=data["action"])

    async def statusAMCS(self) -> None:
        """AMCS status command not to be executed by SAL.

        This command will be used to request the full status of the AMCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.AMCS, self.tel_azimuth)

    async def statusApSCS(self) -> None:
        """ApSCS status command not to be executed by SAL.

        This command will be used to request the full status of the ApSCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.APSCS, self.tel_apertureShutter)

    async def statusLCS(self) -> None:
        """LCS status command not to be executed by SAL.

        This command will be used to request the full status of the LCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.LCS, self.tel_louvers)

    async def statusLWSCS(self) -> None:
        """LWSCS status command not to be executed by SAL.

        This command will be used to request the full status of the LWSCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.LWSCS, self.tel_lightWindScreen)

    async def statusMonCS(self) -> None:
        """MonCS status command not to be executed by SAL.

        This command will be used to request the full status of the MonCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.MONCS, self.tel_interlocks)

    async def statusThCS(self) -> None:
        """ThCS status command not to be executed by SAL.

        This command will be used to request the full status of the ThCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.THCS, self.tel_thermal)

    async def _check_errors_and_send_events_az(
        self, llc_status: dict[str, typing.Any]
    ) -> None:
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        status_message = ", ".join(
            [f"{message['code']}={message['description']}" for message in messages]
        )
        if self.amcs_state != llc_status["status"]:
            self.amcs_state = llc_status["status"]
            self.log.info(f"AMCS state now is {self.amcs_state}")
        if self.amcs_message != status_message:
            self.amcs_message = status_message
            self.log.info(f"AMCS status message now is {self.amcs_message}")
        if len(messages) != 1 or codes[0] != 0:
            await self.evt_azEnabled.set_write(
                state=EnabledState.FAULT, faultCode=status_message
            )
        else:
            await self.evt_azEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

            # TODO DM-37170: Remove as soon as the IDLE state is not used
            #  anymore by the AMCS.
            if llc_status["status"] == "IDLE":
                motion_state = self.previous_state

            if llc_status["status"] in motion_state_translations:
                motion_state = motion_state_translations[llc_status["status"]]
            else:
                motion_state = MotionState[llc_status["status"]]
            in_position = False
            if motion_state in [
                MotionState.STOPPED,
                MotionState.STOPPED_BRAKED,
                MotionState.CRAWLING,
                MotionState.PARKED,
            ]:
                in_position = True

            # In case of some unit tests, this event is expected to be
            # emitted twice with the same data.
            await self.evt_azMotion.set_write(
                state=motion_state, inPosition=in_position
            )

            # TODO DM-37170: Remove as soon as the IDLE state is not used
            #  anymore by the AMCS.
            self.previous_state = motion_state

    async def _check_errors_and_send_events_el(
        self, llc_status: dict[str, typing.Any]
    ) -> None:
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if len(messages) != 1 or codes[0] != 0:
            fault_code = ", ".join(
                [f"{message['code']}={message['description']}" for message in messages]
            )
            await self.evt_elEnabled.set_write(
                state=EnabledState.FAULT, faultCode=fault_code
            )
        else:
            await self.evt_elEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
            if llc_status["status"] in motion_state_translations:
                motion_state = motion_state_translations[llc_status["status"]]
            else:
                motion_state = MotionState[llc_status["status"]]
            in_position = False
            if motion_state in [
                MotionState.STOPPED,
                MotionState.STOPPED_BRAKED,
                MotionState.CRAWLING,
            ]:
                in_position = True
            await self.evt_elMotion.set_write(
                state=motion_state, inPosition=in_position
            )

    async def _check_errors_and_send_events_shutter(
        self, llc_status: dict[str, typing.Any]
    ) -> None:
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if len(messages) != 1 or codes[0] != 0:
            fault_code = ", ".join(
                [f"{message['code']}={message['description']}" for message in messages]
            )
            # Check supported event to make sure of backward compatibility with
            # XML 12.0.
            if hasattr(self, "evt_shutterEnabled"):
                await self.evt_shutterEnabled.set_write(
                    state=EnabledState.FAULT, faultCode=fault_code
                )
        else:
            # Check supported event to make sure of backward compatibility with
            # XML 12.0.
            if hasattr(self, "evt_shutterEnabled"):
                await self.evt_shutterEnabled.set_write(
                    state=EnabledState.ENABLED, faultCode=""
                )
            statuses = llc_status["status"]
            motion_state: list[str] = []
            in_position: list[bool] = []
            # The number of statuses has been validated by the JSON schema. So
            # here it is safe to loop over all statuses.
            for status in statuses:
                if status in motion_state_translations:
                    motion_state.append(motion_state_translations[status])
                else:
                    motion_state.append(MotionState[status])
                in_position.append(
                    status
                    in [
                        MotionState.STOPPED,
                        MotionState.STOPPED_BRAKED,
                    ]
                )
            if hasattr(self, "evt_shutterMotion"):
                await self.evt_shutterMotion.set_write(
                    state=motion_state, inPosition=in_position
                )

    async def request_and_send_llc_status(
        self, llc_name: LlcName, topic: SimpleNamespace
    ) -> None:
        """Generic method for retrieving the status of a lower level component
        and publish that on the corresponding telemetry topic.

        Parameters
        ----------
        llc_name: `LlcName`
            The name of the lower level component.
        topic: SAL topic
            The SAL topic to publish the telemetry to.

        """
        command = f"status{llc_name}"
        status: dict[str, typing.Any] = await self.write_then_read_reply(
            command=command
        )

        if llc_name not in self.lower_level_status:
            # DM-30807: Send OperationalMode event at start up.
            current_operational_mode = status[llc_name]["status"]["operationalMode"]
            operatinal_mode = OperationalMode[current_operational_mode]
            sub_system_id = [
                sid for sid, name in LlcNameDict.items() if name == llc_name
            ][0]
            await self.evt_operationalMode.set_write(
                operationalMode=operatinal_mode,
                subSystemId=sub_system_id,
            )

        # Send appliedConfiguration event for AMCS. This needs to be sent every
        # time the status is read because it can be modified by issuing the
        # config_llcs command. Fortunately salobj only sends events if the
        # values have changed so it is safe to do this without overflowing the
        # EFD with events.
        if llc_name == LlcName.AMCS:
            applied_configuration = status[llc_name]["appliedConfiguration"]
            jmax = math.degrees(applied_configuration["jmax"])
            amax = math.degrees(applied_configuration["amax"])
            vmax = math.degrees(applied_configuration["vmax"])
            await self.evt_azConfigurationApplied.set_write(
                jmax=jmax, amax=amax, vmax=vmax
            )

        # Store the status for reference.
        self.lower_level_status[llc_name] = status[llc_name]

        telemetry_in_degrees: dict[str, typing.Any] = {}
        telemetry_in_radians: dict[str, typing.Any] = status[llc_name]
        for key in telemetry_in_radians.keys():
            if key in _KEYS_IN_RADIANS and llc_name in [LlcName.AMCS, LlcName.LWSCS]:
                telemetry_in_degrees[key] = math.degrees(telemetry_in_radians[key])
                # Compensate for the dome azimuth offset. This is done here and
                # not one level higher since angle_wrap_nonnegative only
                # accepts Angle or a float in degrees and this way the
                # conversion from radians to degrees only is done in one line
                # of code.
                if key in _AMCS_KEYS_OFFSET and llc_name == LlcName.AMCS:
                    offset_value = utils.angle_wrap_nonnegative(
                        telemetry_in_degrees[key] - DOME_AZIMUTH_OFFSET
                    ).degree
                    telemetry_in_degrees[key] = offset_value
            elif key in _APSCS_LIST_KEYS_IN_RADIANS and llc_name == LlcName.APSCS:
                # APSCS key values that are lists can be converted from radians
                # to degrees using numpy.
                telemetry_in_degrees[key] = np.degrees(
                    np.array(telemetry_in_radians[key])
                ).tolist()
            elif key == "timestampUTC":
                # DM-26653: The name of this parameter is still under
                # discussion.
                telemetry_in_degrees["timestamp"] = telemetry_in_radians["timestampUTC"]
            else:
                # No conversion needed since the value does not express an
                # angle.
                telemetry_in_degrees[key] = telemetry_in_radians[key]
        # Remove some keys because they are not reported in the telemetry.
        telemetry: dict[str, typing.Any] = self.remove_keys_from_dict(
            telemetry_in_degrees
        )
        # Send the telemetry.
        await topic.set_write(**telemetry)

        # DM-26374: Check for errors and send the events.
        llc_status = status[llc_name]["status"]
        if llc_name == LlcName.AMCS:
            await self._check_errors_and_send_events_az(llc_status)
        elif llc_name == LlcName.LWSCS:
            await self._check_errors_and_send_events_el(llc_status)
        elif llc_name == LlcName.APSCS:
            await self._check_errors_and_send_events_shutter(llc_status)

    def remove_keys_from_dict(
        self, dict_with_too_many_keys: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        """
        Return a copy of a dict with specified items removed.

        Parameters
        ----------
        dict_with_too_many_keys : `dict`
            The dict where to remove the keys from.

        Returns
        -------
        dict_with_keys_removed : `dict`
            A dict with the same keys as the given dict but with the given keys
            removed.
        """
        dict_with_keys_removed = {
            x: dict_with_too_many_keys[x]
            for x in dict_with_too_many_keys
            if x not in _KEYS_TO_REMOVE
        }
        return dict_with_keys_removed

    async def close_tasks(self) -> None:
        """Disconnect from the TCP/IP controller, if connected, and stop
        the mock controller, if running.
        """
        await super().close_tasks()
        await self.disconnect()

    async def configure(self, config: SimpleNamespace) -> None:
        self.config = config

    async def check_all_commands_have_replies(self) -> None:
        """Check if all commands have received a reply.

        If a command hasn't received a reply after at least
        _COMMANDS_REPLIED_PERIOD seconds, a warning is logged.

        If a command hasn't received a reply after at least 2 *
        _COMMANDS_REPLIED_PERIOD seconds, an error is logged and the command
        is removed from the waiting list.
        """
        current_tai = utils.current_tai()
        commands_to_remove: set[int] = set()
        for command_id in self.commands_without_reply:
            command_time = self.commands_without_reply[command_id]
            if current_tai - command_time.tai >= 2.0 * _COMMANDS_REPLIED_PERIOD:
                self.log.error(
                    f"Command {command_time.command} with {command_id=} has not received a "
                    f"reply during at least {2 * _COMMANDS_REPLIED_PERIOD} seconds. Removing."
                )
                commands_to_remove.add(command_id)
            elif current_tai - command_time.tai >= _COMMANDS_REPLIED_PERIOD:
                self.log.warning(
                    f"Command {command_time.command} with {command_id=} has not received a "
                    f"reply during at least {_COMMANDS_REPLIED_PERIOD} seconds. Still waiting."
                )
        for command_id in commands_to_remove:
            self.commands_without_reply.pop(command_id)

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_mttcs"

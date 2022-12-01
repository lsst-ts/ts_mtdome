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

__all__ = ["MTDomeCsc", "DOME_AZIMUTH_OFFSET", "run_mtdome"]

import asyncio
import math
import typing
from types import SimpleNamespace

import numpy as np
from lsst.ts import salobj, utils
from lsst.ts.idl.enums.MTDome import (
    EnabledState,
    MotionState,
    OperationalMode,
    SubSystemId,
)

from . import __version__, encoding_tools
from .config_schema import CONFIG_SCHEMA
from .csc_utils import support_command
from .enums import (
    LlcName,
    LlcNameDict,
    ResponseCode,
    ValidSimulationMode,
    motion_state_translations,
)
from .llc_configuration_limits import AmcsLimits, LwscsLimits
from .mock_controller import MockMTDomeController

_LOCAL_HOST = "127.0.0.1"
_TIMEOUT = 20  # timeout [sec] to be used by this module
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

# All status methods and the intervals at which they are executed.
ALL_METHODS_AND_INTERVALS = {
    ("statusAMCS", _AMCS_STATUS_PERIOD),
    ("statusApSCS", _APSCS_STATUS_PERIOD),
    ("statusLCS", _LCS_STATUS_PERIOD),
    ("statusLWSCS", _LWSCS_STATUS_PERIOD),
    ("statusMonCS", _MONCS_STATUS_PERIOD),
    ("statusThCS", _THCS_STATUS_PERIOD),
}

# The status methods and the intervals at which they are executed to be used
# during commissioning. Not all can be used because the LabVIEW code of EIE
# doesn't support all of them yet.
METHODS_AND_INTERVALS_FOR_COMMISSIONING = {
    ("statusAMCS", _AMCS_STATUS_PERIOD),
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
    mock_port : `int`
        The port that the mock controller will listen on

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

    enable_cmdline_state = True
    valid_simulation_modes = set([v.value for v in ValidSimulationMode])
    version = __version__

    def __init__(
        self,
        config_dir: typing.Optional[str] = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = ValidSimulationMode.NORMAL_OPERATIONS,
        override: str = "",
        mock_port: typing.Optional[int] = None,
    ) -> None:
        self.reader: typing.Optional[asyncio.StreamReader] = None
        self.writer: typing.Optional[asyncio.StreamWriter] = None
        self.config: typing.Optional[SimpleNamespace] = None

        self.mock_ctrl: typing.Optional[
            MockMTDomeController
        ] = None  # mock controller, or None if not constructed
        self.mock_port = mock_port  # mock port, or None if not used

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
        self.status_tasks: list[asyncio.Future] = []
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

        self.log.info("DomeCsc constructed")

    async def connect(self) -> None:
        """Connect to the dome controller's TCP/IP port.

        Start the mock controller, if simulating.
        """
        self.log.info("connect")
        self.log.info(self.config)
        self.log.info(f"self.simulation_mode = {self.simulation_mode}")
        if self.config is None:
            raise RuntimeError("Not yet configured")
        if self.connected:
            raise RuntimeError("Already connected")
        if self.simulation_mode == ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER:
            await self.start_mock_ctrl()
            host = _LOCAL_HOST
            assert self.mock_ctrl is not None
            port = self.mock_ctrl.port
        elif (
            self.simulation_mode
            == ValidSimulationMode.SIMULATION_WITHOUT_MOCK_CONTROLLER
        ):
            host = _LOCAL_HOST
            assert self.mock_port is not None
            port = self.mock_port
        else:
            host = self.config.host
            port = self.config.port
        try:
            self.log.info(f"Connecting to host={host} and port={port}")
            connect_coro = asyncio.open_connection(host=host, port=port)
            self.reader, self.writer = await asyncio.wait_for(
                connect_coro, timeout=self.config.connection_timeout
            )
        except ConnectionError as e:
            await self.fault(code=3, report=f"Connection to server failed: {e}")
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
        await self.start_status_tasks()

        self.log.info("connected")

    async def cancel_status_tasks(self) -> None:
        """Cancel all status tasks."""
        while self.status_tasks:
            self.status_tasks.pop().cancel()

    async def start_status_tasks(self) -> None:
        """Start all status tasks."""
        await self.cancel_status_tasks()
        methods_and_intervals = ALL_METHODS_AND_INTERVALS
        if self.simulation_mode == ValidSimulationMode.NORMAL_OPERATIONS:
            methods_and_intervals = METHODS_AND_INTERVALS_FOR_COMMISSIONING
        for method, interval in methods_and_intervals:
            func = getattr(self, method)
            self.status_tasks.append(
                asyncio.create_task(self.one_status_loop(func, interval))
            )

    async def disconnect(self) -> None:
        """Disconnect from the TCP/IP controller, if connected, and stop the
        mock controller, if running.
        """
        self.log.info("disconnect")

        # Stop polling for the status of the lower level components
        # periodically.
        await self.cancel_status_tasks()

        writer = self.writer
        self.reader = None
        self.writer = None
        if self.simulation_mode == ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER:
            await self.stop_mock_ctrl()
        if writer:
            try:
                writer.write_eof()
                await asyncio.wait_for(writer.drain(), timeout=_TIMEOUT)
            finally:
                writer.close()

    async def start_mock_ctrl(self) -> None:
        """Start the mock controller.

        The simulation mode must be 1.
        """
        self.log.info("start_mock_ctrl")
        try:
            assert (
                self.simulation_mode
                == ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER.value
            )
            if self.mock_port is not None:
                port = self.mock_port
            else:
                assert self.config is not None
                port = self.config.port
            self.mock_ctrl = MockMTDomeController(port)
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
            await mock_ctrl.stop()

    async def handle_summary_state(self) -> None:
        """Override of the handle_summary_state function to connect or
        disconnect to the lower level components (or the mock_controller) when
        needed.
        """
        self.log.info(f"handle_summary_state {self.summary_state.name}")
        if self.disabled_or_enabled:
            if not self.connected:
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
        command_dict = dict(command=command, parameters=params)
        st = encoding_tools.encode(**command_dict)
        async with self.communication_lock:
            try:
                assert self.writer is not None
            except AssertionError as e:
                await self.fault(code=3, report=f"Error writing command {st}: {e}")
                raise

            disabled_commands: set[str] = set()
            if self.simulation_mode == ValidSimulationMode.NORMAL_OPERATIONS:
                disabled_commands = COMMANDS_DISABLED_FOR_COMMISSIONING

            if command not in disabled_commands:
                self.writer.write(st.encode() + b"\r\n")
                await self.writer.drain()
                try:
                    assert self.reader is not None
                    read_bytes = await asyncio.wait_for(
                        self.reader.readuntil(b"\r\n"), timeout=_TIMEOUT
                    )
                except (
                    asyncio.exceptions.IncompleteReadError,
                    asyncio.exceptions.TimeoutError,
                    ConnectionResetError,
                    AssertionError,
                ) as e:
                    await self.fault(
                        code=3, report=f"Error reading reply to command {st}: {e}"
                    )
                    raise
                data = encoding_tools.decode(read_bytes.decode())
            else:
                data = REPLY_DATA_FOR_DISABLED_COMMANDS
            response = data["response"]

            if response != ResponseCode.OK:
                self.log.error(f"Received ERROR {data}.")
                if response == ResponseCode.COMMAND_REJECTED:
                    raise ValueError(f"The command {command} was rejected.")
                elif response == ResponseCode.UNSUPPORTED_COMMAND:
                    raise KeyError(f"The command {command} is unsupported.")

            return data

    async def do_moveAz(self, data: SimpleNamespace) -> None:
        """Move AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(
            f"Moving Dome to azimuth {data.position} and then start crawling at azRate {data.velocity}"
        )
        # Compensate for the dome azimuth offset.
        position = utils.angle_wrap_nonnegative(
            data.position + DOME_AZIMUTH_OFFSET
        ).degree
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
        self.log.debug(f"Moving LWS to elevation {data.position}")
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
        self.assert_enabled()
        await self.write_then_read_reply(command="setLouvers", position=data.position)

    async def do_closeLouvers(self, data: SimpleNamespace) -> None:
        """Close Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="closeLouvers")

    async def do_openShutter(self, data: SimpleNamespace) -> None:
        """Open Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="openShutter")

    async def do_closeShutter(self, data: SimpleNamespace) -> None:
        """Close Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
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
        await self.write_then_read_reply(command="resetDrivesAz", reset=az_reset)
        if self.simulation_mode != ValidSimulationMode.NORMAL_OPERATIONS:
            aps_reset = [1, 1, 1, 1]
            await self.write_then_read_reply(
                command="resetDrivesShutter", reset=aps_reset
            )
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
            if (
                sub_system_id & sub_system_ids
                and sub_system_id in self.set_home_command_dict
            ):
                command = self.set_home_command_dict[sub_system_id]
                await self.write_then_read_reply(command=command)

    async def config_llcs(self, system: str, settings: dict[str, float]) -> None:
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
        self.log.info(f"Settings before validation {settings}")
        if system == LlcName.AMCS:
            self.amcs_limits.validate(settings)
        elif system == LlcName.LWSCS:
            self.lwscs_limits.validate(settings)
        self.log.info(f"Settings after validation {settings}")

        await self.write_then_read_reply(
            command="config", system=system, settings=settings
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

            # DM-34664: Send appliedConfiguration event as well, if present.
            if "appliedConfiguration" in status[llc_name]:
                applied_configuration = status[llc_name]["appliedConfiguration"]
                jmax = applied_configuration["jmax"]
                amax = applied_configuration["amax"]
                vmax = applied_configuration["vmax"]
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

    async def one_status_loop(self, method: typing.Callable, interval: float) -> None:
        """Run one status method forever at the specified interval.

        Parameters
        ----------
        method: coro
            The status method to run
        interval: `float`
            The interval (sec) at which to run the status method.

        """
        try:
            while True:
                await method()
                await asyncio.sleep(interval)
        except Exception:
            self.log.exception(f"one_status_loop({method}) failed")

    @property
    def connected(self) -> bool:
        """Return True if connected to a server."""
        return not (
            self.reader is None
            or self.writer is None
            or self.reader.at_eof()
            or self.writer.is_closing()
        )

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_mttcs"

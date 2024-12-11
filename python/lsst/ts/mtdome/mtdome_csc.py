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

__all__ = ["MTDomeCsc", "run_mtdome"]

import asyncio
import math
import typing
from types import SimpleNamespace

from lsst.ts import mtdomecom, salobj
from lsst.ts.mtdomecom.enums import (
    CommandName,
    LlcName,
    LlcNameDict,
    MaxValueConfigType,
    ValidSimulationMode,
    motion_state_translations,
)
from lsst.ts.xml.enums.MTDome import (
    EnabledState,
    MotionState,
    OperationalMode,
    PowerManagementMode,
)

from . import __version__
from .config_schema import CONFIG_SCHEMA

# Timeout [sec] used when creating a Client, a mock controller or when waiting
# for a reply when sending a command to the controller.
_TIMEOUT = 20

_KEYS_TO_REMOVE = {
    "status",
    "operationalMode",  # Remove because gets emitted as an event
    "appliedConfiguration",  # Remove because gets emitted as an event
}

# Polling periods [sec] for the lower level components.
_AMCS_STATUS_PERIOD = 0.2
_APSCS_STATUS_PERIOD = 0.5
_CBCS_STATUS_PERIOD = 0.5
_CSCS_STATUS_PERIOD = 0.5
_LCS_STATUS_PERIOD = 0.5
_LWSCS_STATUS_PERIOD = 0.5
_MONCS_STATUS_PERIOD = 0.5
_RAD_STATUS_PERIOD = 0.5
_THCS_STATUS_PERIOD = 0.5

# Polling period [sec] for the task that checks if any commands are waiting to
# be issued.
_COMMAND_QUEUE_PERIOD = 1.0


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

    # All methods and the intervals at which they are executed. Note that all
    # methods are disabled for unit testing unless the specific test case
    # reqiures one of more to be available.
    all_methods_and_intervals = {
        CommandName.STATUS_AMCS: _AMCS_STATUS_PERIOD,
        # CommandName.STATUS_APSCS: _APSCS_STATUS_PERIOD,
        CommandName.STATUS_CBCS: _CBCS_STATUS_PERIOD,
        # CommandName.STATUS_CSCS: _CSCS_STATUS_PERIOD,
        # CommandName.STATUS_LCS: _LCS_STATUS_PERIOD,
        # CommandName.STATUS_LWSCS: _LWSCS_STATUS_PERIOD,
        # CommandName.STATUS_MONCS: _MONCS_STATUS_PERIOD,
        # CommandName.STATUS_RAD: _RAD_STATUS_PERIOD,
        # CommandName.STATUS_THCS: _THCS_STATUS_PERIOD,
    }

    def __init__(
        self,
        config_dir: str | None = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = ValidSimulationMode.NORMAL_OPERATIONS,
        override: str = "",
    ) -> None:
        self.config: SimpleNamespace | None = None

        super().__init__(
            name="MTDome",
            index=0,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
            override=override,
        )

        # MTDome TCP/IP communicator.
        self.mtdome_com: mtdomecom.MTDomeCom | None = None

        # List of periodic tasks to start.
        self.periodic_tasks: list[asyncio.Future] = []
        # Keep track of the AMCS state for logging one the console.
        self.amcs_state: MotionState | None = None
        # Keep track of the AMCS status message for logging on the console.
        self.amcs_message: str = ""

        self.log.info("DomeCsc constructed.")

    async def connect(self) -> None:
        """Connect to the dome controller's TCP/IP port.

        Start the mock controller, if simulating.
        """
        assert self.config is not None
        self.mtdome_com = mtdomecom.MTDomeCom(
            log=self.log, config=self.config, simulation_mode=self.simulation_mode
        )
        try:
            await self.mtdome_com.connect()
        except Exception as e:
            await self.fault(code=3, report=f"Connection to server failed: {e!r}.")
            raise

        await self.evt_azEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        await self.evt_elEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        await self.evt_shutterEnabled.set_write(
            state=EnabledState.ENABLED, faultCode=""
        )

        await self.evt_brakesEngaged.set_write(brakes=0)
        await self.evt_interlocks.set_write(interlocks=0)
        await self.evt_lockingPinsEngaged.set_write(engaged=0)

        await self.evt_powerManagementMode.set_write(
            mode=self.mtdome_com.power_management_mode
        )

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
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.config_llcs, system=LlcName.AMCS, settings=settings
        )

    async def cancel_periodic_tasks(self) -> None:
        """Cancel all periodic tasks."""
        while self.periodic_tasks:
            periodic_task = self.periodic_tasks.pop()
            periodic_task.cancel()
            await periodic_task

    async def start_periodic_tasks(self) -> None:
        """Start all periodic tasks."""
        await self.cancel_periodic_tasks()
        for method, interval in self.all_methods_and_intervals.items():
            func = getattr(self, method)
            self.periodic_tasks.append(
                asyncio.create_task(self.one_periodic_task(func, interval))
            )

        assert self.mtdome_com is not None
        self.periodic_tasks.append(
            asyncio.create_task(
                self.one_periodic_task(
                    self.mtdome_com.check_all_commands_have_replies,
                    mtdomecom.COMMANDS_REPLIED_PERIOD,
                    True,
                )
            )
        )

        self.periodic_tasks.append(
            asyncio.create_task(
                self.one_periodic_task(
                    self.mtdome_com.process_command_queue, _COMMAND_QUEUE_PERIOD, True
                )
            )
        )

    async def one_periodic_task(
        self, method: typing.Callable, interval: float, go_fault: bool = False
    ) -> None:
        """Run one method forever at the specified interval.

        Parameters
        ----------
        method : `typing.Callable`
            The periodic method to run.
        interval : `float`
            The interval (sec) at which to run the status method.
        go_fault : `bool`
            Make the CSC go to FAULT state (True) or not (Fault). Defaults to
            Fault.

        """
        self.log.debug(f"Starting periodic task {method=} with {interval=}")
        try:
            while True:
                await method()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            # Ignore because the task was canceled on purpose.
            pass
        except Exception:
            self.log.exception(f"one_periodic_task({method}) has stopped.")
            if go_fault:
                await self.go_fault(method)

    async def disconnect(self) -> None:
        """Disconnect from the TCP/IP controller, if connected, and stop the
        mock controller, if running.
        """
        self.log.info("disconnect.")

        # Stop all periodic tasks, including polling for the status of the
        # lower level components.
        await self.cancel_periodic_tasks()

        if self.connected:
            assert self.mtdome_com is not None
            await self.mtdome_com.disconnect()
            self.mtdome_com = None

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

    async def end_enable(self, data: salobj.BaseMsgType) -> None:
        """End do_enable; called after state changes
        but before command acknowledged.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Command data.
        """
        await super().end_enable(data)

        assert self.config is not None
        if (
            self.config.amcs_vmax > 0
            and self.config.amcs_amax > 0
            and self.config.amcs_jmax > 0
        ):
            await self._set_maximum_motion_values()
        else:
            self.log.info("Not setting AMCS maximum velocity, acceleration and jerk.")

    async def do_moveAz(self, data: salobj.BaseMsgType) -> None:
        """Move AZ.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"do_moveAz: {data.position=!s}, {data.velocity=!s}")
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.move_az,
            position=data.position,
            velocity=data.velocity,
        )
        await self.evt_azEnabled.set_write(
            state=EnabledState.ENABLED,
            faultCode="",
        )
        await self.evt_azTarget.set_write(
            position=data.position, velocity=data.velocity
        )

    async def do_moveEl(self, data: salobj.BaseMsgType) -> None:
        """Move El.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"do_moveEl: {data.position=!s}")
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.move_el, position=data.position)
        await self.evt_elTarget.set_write(position=data.position, velocity=0)

    async def do_stop(self, data: salobj.BaseMsgType) -> None:
        """Stop all motion and engage the brakes if indicated in the data.
        Also disengage the locking pins if engaged.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.stop_sub_systems,
            sub_system_ids=data.subSystemIds,
            engage_brakes=data.engageBrakes,
        )

    async def do_crawlAz(self, data: salobj.BaseMsgType) -> None:
        """Crawl AZ.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_crawlAz: {data.velocity=!s}")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.crawl_az, velocity=data.velocity)
        await self.evt_azTarget.set_write(position=float("nan"), velocity=data.velocity)

    async def do_crawlEl(self, data: salobj.BaseMsgType) -> None:
        """Crawl El.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_crawlEl: {data.velocity=!s}")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.crawl_el, velocity=data.velocity)
        await self.evt_elTarget.set_write(position=float("nan"), velocity=data.velocity)

    async def do_setLouvers(self, data: salobj.BaseMsgType) -> None:
        """Set Louver.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_setLouvers: {data.position=!s}")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.set_louvers, position=data.position
        )

    async def do_closeLouvers(self, data: salobj.BaseMsgType) -> None:
        """Close Louvers.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_closeLouvers")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.close_louvers)

    async def do_openShutter(self, data: salobj.BaseMsgType) -> None:
        """Open Shutter.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_openShutter")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.open_shutter)

    async def do_closeShutter(self, data: salobj.BaseMsgType) -> None:
        """Close Shutter.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_closeShutter")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.close_shutter)

    async def do_park(self, data: salobj.BaseMsgType) -> None:
        """Park, meaning stop all motion and engage the brakes and locking
        pins.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_park")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.park)
        await self.evt_azTarget.set_write(
            position=360.0 - mtdomecom.DOME_AZIMUTH_OFFSET, velocity=0
        )

    async def do_setTemperature(self, data: salobj.BaseMsgType) -> None:
        """Set Temperature.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_setTemperature: {data.temperature=!s}")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.set_temperature, temperature=data.temperature
        )

    async def do_exitFault(self, data: salobj.BaseMsgType) -> None:
        """Indicate that all hardware errors, leading to fault state, have been
        resolved.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug("do_exitFault")
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.exit_fault)

    async def do_setOperationalMode(self, data: salobj.BaseMsgType) -> None:
        """Indicate that one or more sub_systems need to operate in degraded
        (true) or normal (false) state.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        operational_mode = OperationalMode(data.operationalMode)
        self.log.debug(f"do_setOperationalMode: {operational_mode=}")
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.set_operational_mode,
            operational_mode=operational_mode,
            sub_system_ids=data.subSystemIds,
        )

    async def do_resetDrivesAz(self, data: salobj.BaseMsgType) -> None:
        """Reset one or more AZ drives. This is necessary when exiting from
        FAULT state without going to Degraded Mode since the drives don't reset
        themselves.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        reset_ints = [int(value) for value in data.reset]
        self.log.debug(f"do_resetDrivesAz: reset={reset_ints}")
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.reset_drives_az, reset=reset_ints)

    async def do_resetDrivesShutter(self, data: salobj.BaseMsgType) -> None:
        """Reset one or more Aperture Shutter drives. This is necessary when
        exiting from FAULT state without going to Degraded Mode since the
        drives don't reset themselves.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        reset_ints = [int(value) for value in data.reset]
        self.log.debug(f"do_resetDrivesShutter: reset={reset_ints}")
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.reset_drives_shutter, reset=reset_ints
        )

    async def do_setZeroAz(self, data: salobj.BaseMsgType) -> None:
        """Take the current position of the dome as zero. This is necessary as
        long as the racks and pinions on the drives have not been installed yet
        to compensate for slippage of the drives.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug("do_setZeroAz")
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.set_zero_az)

    async def do_home(self, data: salobj.BaseMsgType) -> None:
        """Search the home position of the Aperture Shutter, which is the
        closed position.

        This is necessary in case the ApSCS (Aperture Shutter Control system)
        was shutdown with the Aperture Shutter not fully open or fully closed.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.home, sub_system_ids=data.subSystemIds
        )

    async def restore_llcs(self) -> None:
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.restore_llcs)

    async def do_fans(self, data: salobj.BaseMsgType) -> None:
        """Set the speed of the fans.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"do_fans: {data.speed=!s}")
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.fans, speed=data.speed)

    async def do_inflate(self, data: salobj.BaseMsgType) -> None:
        """Inflate or deflate the inflatable seal.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"do_inflate: {data.action=!s}")
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.inflate, action=data.action)

    async def do_setPowerManagementMode(self, data: salobj.BaseMsgType) -> None:
        """Set the power management mode.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.

        Raises
        ------
        salobj.ExpectedError
            In case data.mode is equal to NO_POWER_MANAGEMENT.

        Notes
        -----
        In case data.mode is equal to the current mode, a warning is logged and
        the new mode is ignored.
        """
        self.assert_enabled()

        new_mode = PowerManagementMode(data.mode)
        assert self.mtdome_com is not None
        await self.call_method(
            method=self.mtdome_com.set_power_management_mode,
            power_management_mode=new_mode,
        )
        await self.evt_powerManagementMode.set_write(
            mode=self.mtdome_com.power_management_mode
        )

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

    async def statusCBCS(self) -> None:
        """CBCS status command not to be executed by SAL.

        This command will be used to request the full status of the CBCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.CBCS, self.evt_capacitorBanks)

    async def statusCSCS(self) -> None:
        """CSCS status command not to be executed by SAL.

        This command will be used to request the full status of the CSCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.CSCS, self.tel_calibrationScreen)

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

    async def statusRAD(self) -> None:
        """RAD status command not to be executed by SAL.

        This command will be used to request the full status of the RAD lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.RAD, self.tel_rearAccessDoor)

    async def statusThCS(self) -> None:
        """ThCS status command not to be executed by SAL.

        This command will be used to request the full status of the ThCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.THCS, self.tel_thermal)

    def _translate_motion_state_if_necessary(self, state: str) -> MotionState:
        try:
            motion_state = MotionState[state]
        except KeyError:
            motion_state = motion_state_translations[state]
        return motion_state

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

            motion_state = self._translate_motion_state_if_necessary(
                llc_status["status"]
            )
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
            motion_state = self._translate_motion_state_if_necessary(
                llc_status["status"]
            )
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
                motion_state.append(self._translate_motion_state_if_necessary(status))
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
        assert self.mtdome_com is not None
        try:
            status: dict[str, typing.Any] = await self.call_method(
                method=self.mtdome_com.request_llc_status, llc_name=llc_name
            )
        except ValueError:
            # An error message is logged in `self.write_then_read_reply`.
            return

        await self._send_operational_mode_event(llc_name=llc_name, status=status)
        await self._send_applied_configuration_event(llc_name, status)

        # Remove some keys because they are not reported in the telemetry.
        pre_processed_telemetry = self._remove_keys_from_dict(status)

        # Avoid sending this event 2x per second due to a changing timestamp.
        if topic == self.evt_capacitorBanks and "timestamp" in pre_processed_telemetry:
            del pre_processed_telemetry["timestamp"]

        # Send the telemetry.
        await topic.set_write(**pre_processed_telemetry)
        await self._check_errors_and_send_events(
            llc_name=llc_name, llc_status=status["status"]
        )

    async def _send_applied_configuration_event(
        self, llc_name: str, status: dict[str, typing.Any]
    ) -> None:
        # Send appliedConfiguration event for AMCS. This needs to be sent every
        # time the status is read because it can be modified by issuing the
        # config_llcs command. Fortunately salobj only sends events if the
        # values have changed so it is safe to do this without overflowing the
        # EFD with events.
        if llc_name == LlcName.AMCS.value:
            if "appliedConfiguration" in status:
                applied_configuration = status["appliedConfiguration"]
                jmax = math.degrees(applied_configuration["jmax"])
                amax = math.degrees(applied_configuration["amax"])
                vmax = math.degrees(applied_configuration["vmax"])
                await self.evt_azConfigurationApplied.set_write(
                    jmax=jmax, amax=amax, vmax=vmax
                )
            else:
                self.log.warning(
                    "No 'appliedConfiguration' in AMCS telemetry. "
                    "Not sending the azConfigurationApplied event."
                )

    async def _send_operational_mode_event(
        self, llc_name: str, status: dict[str, typing.Any]
    ) -> None:
        if "operationalMode" in status["status"]:
            # DM-30807: Send OperationalMode event at start up.
            current_operational_mode = status["status"]["operationalMode"]
            operatinal_mode = OperationalMode[current_operational_mode]
            sub_system_id = [
                sid for sid, name in LlcNameDict.items() if name == llc_name
            ][0]
            await self.evt_operationalMode.set_write(
                operationalMode=operatinal_mode,
                subSystemId=sub_system_id,
            )

    async def _check_errors_and_send_events(
        self, llc_name: str, llc_status: dict[str, typing.Any]
    ) -> None:
        # DM-26374: Check for errors and send the events.
        if llc_name == LlcName.AMCS.value:
            await self._check_errors_and_send_events_az(llc_status)
        elif llc_name == LlcName.LWSCS.value:
            await self._check_errors_and_send_events_el(llc_status)
        elif llc_name == LlcName.APSCS.value:
            await self._check_errors_and_send_events_shutter(llc_status)

    def _remove_keys_from_dict(
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

    async def call_method(
        self, method: typing.Callable, **kwargs: typing.Any
    ) -> typing.Any:
        """Generic method for error handling when calling a method.

        Parameters
        ----------
        method : `typing.Callable`
            The method that needs generic error handling.
        kwargs : `typing.Any`
            The arguments for the method.

        Raises
        ------
        ValuesError
            This is an expected error when calling the method fails. All other
            errors will lead to the CSC going to FAULT state.

        """
        try:
            return await method(**kwargs)
        except ValueError:
            raise
        except Exception:
            await self.go_fault(method)

    async def go_fault(self, method: typing.Callable) -> None:
        """Convenience method to go to FAULT state.

        Parameters
        ----------
        method : `typing.Callable`
            The method that causes the FAULT state.
        """
        await self.fault(code=3, report=f"Error calling {method=}.")

    @property
    def connected(self) -> bool:
        return (
            self.mtdome_com is not None
            and self.mtdome_com.client is not None
            and self.mtdome_com.client.connected
        )

    @staticmethod
    def get_config_pkg() -> str:
        return "ts_config_mttcs"

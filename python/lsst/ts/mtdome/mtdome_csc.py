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
import traceback
import typing
from types import SimpleNamespace

from lsst.ts import mtdomecom, salobj
from lsst.ts.mtdomecom.enums import (
    BRAKES_ENGAGED_STATES,
    LlcName,
    LlcNameDict,
    ValidSimulationMode,
    motion_state_translations,
)
from lsst.ts.xml.enums.MTDome import (
    EnabledState,
    Louver,
    MotionState,
    OperationalMode,
    PowerManagementMode,
)

from . import __version__
from .config_schema import CONFIG_SCHEMA

# TODO OSW-1491 Remove backward compatibility with XML 24.3
TWENTYFOUR_THREE = "24.3"
TWENTYFOUR_FOUR = "24.4"
try:
    from lsst.ts.xml.enums.MTDome import Brake, ControlMode

    XML_VERSION = TWENTYFOUR_FOUR
except ImportError:
    from lsst.ts.mtdomecom import Brake, ControlMode

    XML_VERSION = TWENTYFOUR_THREE

_KEYS_TO_REMOVE = {
    "status",
    "operationalMode",  # Remove because gets emitted as an event
    "appliedConfiguration",  # Remove because gets emitted as an event
}

# Time [s] to sleep after an exception in a status command.
EXCEPTION_SLEEP_TIME = 1.0


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
    start_periodic_tasks : `bool`
        Start the periodic tasks or not. Defaults to `True`. Unit tests may set
        this to `False`.

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
        config_dir: str | None = None,
        initial_state: salobj.State = salobj.State.STANDBY,
        simulation_mode: int = ValidSimulationMode.NORMAL_OPERATIONS,
        override: str = "",
        start_periodic_tasks: bool = True,
    ) -> None:
        self.config: SimpleNamespace | None = None
        self.start_periodic_tasks = start_periodic_tasks

        setattr(self, "do_resetDrivesLouvers", self._do_resetDrivesLouvers)

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

        # Keep track of the AMCS state for logging on the console.
        self.amcs_state: MotionState | None = None
        # Keep track of the LCS state for logging on the console.
        self.lcs_state: MotionState | None = None
        # Keep track of the ApSCS state for logging on the console.
        self.apscs_state: MotionState | None = None
        # Keep track of the RAD state for logging on the console.
        self.rad_state: MotionState | None = None
        # Keep track of the CSCS state for logging on the console.
        self.cscs_state: MotionState | None = None
        # Keep track of the AMCS status message for logging on the console.
        self.amcs_message: str = ""
        # Keep track of the operational modes of the LLCs to avoid emitting
        # redundant events.
        self.llc_operational_modes: dict[LlcName, OperationalMode | None] = {}

        # Keep track of which brakes are engaged.
        self.brakes_engaged_bitmask = 0

        self.reject_small_azimuth_motions = False

        # Unit tests may set this to False for additional checks.
        self.set_mtdomecom_to_none = True

        self.log.info("DomeCsc constructed.")

    async def connect(self) -> None:
        """Connect to the dome controller's TCP/IP port.

        Start the mock controller, if simulating.
        """
        self.log.info("connect.")

        assert self.config is not None
        if hasattr(self.config, "reject_small_azimuth_motions"):
            self.reject_small_azimuth_motions = self.config.reject_small_azimuth_motions
        self.log.debug(f"Rejecting small azimuth motions? {self.reject_small_azimuth_motions=}")

        callbacks_for_operations = {
            LlcName.AMCS: self.status_amcs,
            LlcName.APSCS: self.status_apscs,
            LlcName.LCS: self.status_lcs,
            LlcName.CBCS: self.status_cbcs,
            LlcName.THCS: self.status_thcs,
        }

        callbacks_for_simulation = callbacks_for_operations | {
            LlcName.LLC: self.status_llc,
            LlcName.CSCS: self.status_cscs,
            LlcName.LWSCS: self.status_lwscs,
            LlcName.MONCS: self.status_moncs,
            LlcName.RAD: self.status_rad,
        }

        telemetry_callbacks = (
            callbacks_for_operations
            if self.simulation_mode == ValidSimulationMode.NORMAL_OPERATIONS
            else callbacks_for_simulation
        )

        # Make sure that the correct port is used.
        self.config.port = self.config.csc_port
        self.mtdome_com = mtdomecom.MTDomeCom(
            log=self.log,
            config=self.config,
            config_dir=self.config_dir,
            simulation_mode=self.simulation_mode,
            telemetry_callbacks=telemetry_callbacks,
            reject_small_azimuth_motions=self.reject_small_azimuth_motions,
            start_periodic_tasks=self.start_periodic_tasks,
        )
        try:
            await self.mtdome_com.connect()
        except Exception as e:
            await self.fault(code=3, report=f"Connection to server failed: {e!r}.")
            raise

        await self.evt_azEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        await self.evt_elEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        await self.evt_louversEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
        await self.evt_shutterEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_radEnabled.set_write(state=EnabledState.ENABLED, faultCode="")
            await self.evt_calibrationScreenEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        # Report ENABLED and DISABLED louvers.
        louvers_motion_state: list[MotionState] = [MotionState.DISABLED] * mtdomecom.LCS_NUM_LOUVERS
        for louver in self.mtdome_com.louvers_enabled:
            louvers_motion_state[louver.value - 1] = MotionState.ENABLED
        await self.evt_louversMotion.set_write(
            state=louvers_motion_state, inPosition=[True] * mtdomecom.LCS_NUM_LOUVERS
        )

        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)
        await self.evt_interlocks.set_write(interlocks=0)
        await self.evt_lockingPinsEngaged.set_write(engaged=0)
        await self.evt_powerManagementMode.set_write(mode=self.mtdome_com.power_management_mode)

        self.log.info("connected")

    async def _set_maximum_motion_values(self) -> None:
        assert self.config is not None
        vmax = self.config.amcs_vmax
        amax = self.config.amcs_amax
        jmax = self.config.amcs_jmax
        self.log.debug(f"Setting AMCS maximum velocity to {vmax}.")
        vmax_dict = {"target": "vmax", "setting": [vmax]}
        self.log.debug(f"Setting AMCS maximum acceleration to {amax}.")
        amax_dict = {"target": "amax", "setting": [amax]}
        self.log.debug(f"Setting AMCS maximum jerk to {jmax}.")
        jmax_dict = {"target": "jmax", "setting": [jmax]}
        settings = [vmax_dict, amax_dict, jmax_dict]
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.config_llcs, system=LlcName.AMCS, settings=settings)

    async def disconnect(self) -> None:
        """Disconnect from the TCP/IP controller, if connected, and stop the
        mock controller, if running.
        """
        self.log.info("disconnect.")

        if self.connected:
            assert self.mtdome_com is not None
            await self.mtdome_com.disconnect()

        if self.set_mtdomecom_to_none:
            self.mtdome_com = None

    async def handle_summary_state(self) -> None:
        """Override of the handle_summary_state function to connect or
        disconnect to the lower level components (or the mock_controller) when
        needed.
        """
        self.log.debug(f"handle_summary_state {self.summary_state.name}")
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
        if self.config.amcs_vmax > 0 and self.config.amcs_amax > 0 and self.config.amcs_jmax > 0:
            await self._set_maximum_motion_values()
        else:
            self.log.debug("Not setting AMCS maximum velocity, acceleration and jerk.")

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
        await self.evt_azTarget.set_write(position=data.position, velocity=data.velocity)

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
        """Set the louver positions.

        This method checks if all commanded louvers are enabled and will
        reject the command if any are not.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.log.debug(f"do_setLouvers: {data.position=!s}")
        self.assert_enabled()
        assert self.mtdome_com is not None
        disabled_louvers: list[Louver] = []
        for i, position in enumerate(data.position):
            louver = Louver(i + 1)
            if louver not in self.mtdome_com.louvers_enabled and position > 0.0:
                disabled_louvers.append(louver)
        if len(disabled_louvers) > 0:
            raise salobj.ExpectedError(
                f"The following louvers are not enabled and should not be commanded: {disabled_louvers}"
            )
        await self.call_method(method=self.mtdome_com.set_louvers, position=data.position)

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
        await self.evt_azTarget.set_write(position=360.0 - mtdomecom.DOME_AZIMUTH_OFFSET, velocity=0)

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
        await self.call_method(method=self.mtdome_com.set_temperature, temperature=data.temperature)

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
        await self.call_method(method=self.mtdome_com.exit_fault, sub_system_ids=data.subSystemIds)

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
        await self.call_method(method=self.mtdome_com.reset_drives_shutter, reset=reset_ints)

    async def _do_resetDrivesLouvers(self, data: salobj.BaseMsgType) -> None:
        """Reset one or more Louver drives. This is necessary when
        exiting from FAULT state without going to Degraded Mode since the
        drives don't reset themselves.

        Parameters
        ----------
        data : `salobj.BaseMsgType`
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        reset_ints = [int(value) for value in data.reset]
        self.log.debug(f"do_resetDrivesLouvers: reset={reset_ints}")
        assert self.mtdome_com is not None
        await self.call_method(method=self.mtdome_com.reset_drives_louvers, reset=reset_ints)

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
        """Search the home position of the Aperture Shutter indicated by the
        value of `direction` in `data`.

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
            method=self.mtdome_com.home,
            sub_system_ids=data.subSystemIds,
            direction=[data.direction, data.direction],
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
        await self.evt_powerManagementMode.set_write(mode=self.mtdome_com.power_management_mode)

    async def log_status_exception(self, status: dict[str, typing.Any]) -> None:
        self.log.exception(status["exception"])
        await asyncio.sleep(EXCEPTION_SLEEP_TIME)

    async def status_amcs(self, status: dict[str, typing.Any]) -> None:
        """AMCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        else:
            applied_configuration = status["appliedConfiguration"]
            jmax = math.degrees(applied_configuration["jmax"])
            amax = math.degrees(applied_configuration["amax"])
            vmax = math.degrees(applied_configuration["vmax"])
            await self.evt_azConfigurationApplied.set_write(jmax=jmax, amax=amax, vmax=vmax)

        await self.send_llc_status_telemetry_and_events(LlcName.AMCS, status, self.tel_azimuth)

    async def status_apscs(self, status: dict[str, typing.Any]) -> None:
        """ApSCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        self.log.debug("status_apscs")
        if "exception" in status:
            await self.log_status_exception(status)
        await self.send_llc_status_telemetry_and_events(LlcName.APSCS, status, self.tel_apertureShutter)

    async def status_cbcs(self, status: dict[str, typing.Any]) -> None:
        """CBCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        else:
            dc_bus_voltage = status.pop("dcBusVoltage")
            # Send the capacitor banks telemetry.
            await self.tel_capacitorBanks.set_write(dcBusVoltage=dc_bus_voltage)
        await self.send_llc_status_telemetry_and_events(LlcName.CBCS, status, self.evt_capacitorBanks)

    async def status_llc(self, status: dict[str, typing.Any]) -> None:
        """LLC status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        else:
            control_mode = ControlMode[status["control_mode"]]
            # TODO OSW-1491 Remove backward compatibility with XML 24.3
            if XML_VERSION == TWENTYFOUR_FOUR:
                await self.evt_controlMode.set_write(mode=control_mode.value)

    async def status_cscs(self, status: dict[str, typing.Any]) -> None:
        """CSCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        await self.send_llc_status_telemetry_and_events(LlcName.CSCS, status, self.tel_calibrationScreen)

    async def status_lcs(self, status: dict[str, typing.Any]) -> None:
        """LCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        await self.send_llc_status_telemetry_and_events(LlcName.LCS, status, self.tel_louvers)

    async def status_lwscs(self, status: dict[str, typing.Any]) -> None:
        """LWSCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        await self.send_llc_status_telemetry_and_events(LlcName.LWSCS, status, self.tel_lightWindScreen)

    async def status_moncs(self, status: dict[str, typing.Any]) -> None:
        """MonCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        await self.send_llc_status_telemetry_and_events(LlcName.MONCS, status, self.tel_interlocks)

    async def status_rad(self, status: dict[str, typing.Any]) -> None:
        """RAD status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)
        await self.send_llc_status_telemetry_and_events(LlcName.RAD, status, self.tel_rearAccessDoor)

    async def status_thcs(self, status: dict[str, typing.Any]) -> None:
        """ThCS status command.

        Parameters
        ----------
        status : `dict` [`str`, `typing.Any`]
            The status.
        """
        if "exception" in status:
            await self.log_status_exception(status)

        await self.send_llc_status_telemetry_and_events(LlcName.THCS, status, self.tel_thermal)

    async def send_llc_status_telemetry_and_events(
        self, llc_name: LlcName, status: dict[str, typing.Any], topic: SimpleNamespace
    ) -> None:
        """Generic method for publishing the telemetry and events of a lower
        level component.

        Parameters
        ----------
        llc_name: `LlcName`
            The name of the lower level component.
        status : `dict` [`str`, `typing.Any`]
            The status.
        topic: SAL topic
            The SAL topic to publish the telemetry to.
        """
        assert self.mtdome_com is not None

        # Send the operational mode event.
        await self._send_operational_mode_event(llc_name=llc_name, status=status)

        if "exception" not in status:
            # Send the telemetry.
            telemetry = self.mtdome_com.remove_keys_from_dict(status, _KEYS_TO_REMOVE)
            await topic.set_write(**telemetry)

            await self._check_errors_and_send_events(llc_name=llc_name, llc_status=status["status"])
        else:
            await self._handle_command_exception(status)

    async def _send_operational_mode_event(self, llc_name: LlcName, status: dict[str, typing.Any]) -> None:
        if "status" in status and "operationalMode" in status["status"]:
            self.log.debug(f"Sending operational mode event for {llc_name}.")

            if llc_name not in self.llc_operational_modes:
                self.llc_operational_modes[llc_name] = None

            current_operational_mode = status["status"]["operationalMode"]
            operational_mode = OperationalMode[current_operational_mode]
            if self.llc_operational_modes[llc_name] != operational_mode:
                self.llc_operational_modes[llc_name] = operational_mode
                sub_system_id = [sid for sid, name in LlcNameDict.items() if name == llc_name][0]
                await self.evt_operationalMode.set_write(
                    operationalMode=operational_mode,
                    subSystemId=sub_system_id,
                )

    async def _check_errors_and_send_events(self, llc_name: str, llc_status: dict[str, typing.Any]) -> None:
        """Check errors and send events.

        Parameters
        ----------
        llc_name : `str`
            The name of the lower level component.
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        if llc_name == LlcName.AMCS.value:
            await self._check_errors_and_send_events_az(llc_status)
        elif llc_name == LlcName.LWSCS.value:
            await self._check_errors_and_send_events_el(llc_status)
        elif llc_name == LlcName.APSCS.value:
            await self._check_errors_and_send_events_shutter(llc_status)
        elif llc_name == LlcName.LCS.value:
            await self._check_errors_and_send_events_louvers(llc_status)
        elif llc_name == LlcName.RAD.value:
            await self._check_errors_and_send_events_rad(llc_status)
        elif llc_name == LlcName.CSCS.value:
            await self._check_errors_and_send_events_calibration_screen(llc_status)

    async def _check_errors_and_send_events_az(self, llc_status: dict[str, typing.Any]) -> None:
        """Check errors and send events for the azimuth rotation.

        Parameters
        ----------
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        messages = llc_status["messages"]
        status_message = ", ".join([f"{message['code']}={message['description']}" for message in messages])
        if self.amcs_state != llc_status["status"]:
            self.amcs_state = llc_status["status"]
            self.log.debug(f"AMCS state now is {self.amcs_state}")
        if self.amcs_message != status_message:
            self.amcs_message = status_message
            self.log.info(f"AMCS status message now is {self.amcs_message}")
            await self.evt_azEnabled.set_write(state=EnabledState.FAULT, faultCode=status_message)
        else:
            await self.evt_azEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        motion_state = self._translate_motion_state_if_necessary(llc_status["status"])
        in_position = False
        if motion_state in [
            MotionState.STOPPED,
            MotionState.STOPPED_BRAKED,
            MotionState.CRAWLING,
            MotionState.PARKED,
        ]:
            in_position = True

        await self.evt_azMotion.set_write(state=motion_state, inPosition=in_position)
        await self.set_brakes_engaged_bit(motion_state, Brake.AMCS.value)
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)

    async def _check_errors_and_send_events_el(self, llc_status: dict[str, typing.Any]) -> None:
        """Check errors and send events for the light/windscreen (elevation
        direction).

        Parameters
        ----------
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if len(messages) != 1 or codes[0] != 0:
            fault_code = ", ".join([f"{message['code']}={message['description']}" for message in messages])
            await self.evt_elEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
        else:
            await self.evt_elEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        motion_state = self._translate_motion_state_if_necessary(llc_status["status"])
        in_position = False
        if motion_state in [
            MotionState.STOPPED,
            MotionState.STOPPED_BRAKED,
            MotionState.CRAWLING,
        ]:
            in_position = True
        await self.evt_elMotion.set_write(state=motion_state, inPosition=in_position)
        await self.set_brakes_engaged_bit(motion_state, Brake.LWSCS.value)
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)

    async def _check_errors_and_send_events_louvers(self, llc_status: dict[str, typing.Any]) -> None:
        """Check errors and send events for the louvers.

        Parameters
        ----------
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if self.lcs_state != llc_status["status"]:
            self.lcs_state = llc_status["status"]
            self.log.debug(f"LCS state now is {self.lcs_state}")
        if len(messages) != 1 or codes[0] != 0:
            fault_code = ", ".join([f"{message['code']}={message['description']}" for message in messages])
            await self.evt_louversEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
        else:
            await self.evt_louversEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        statuses = llc_status["status"]
        motion_state: list[str] = []
        in_position: list[bool] = []

        # The number of statuses has been validated by the JSON schema. So
        # here it is safe to loop over all statuses.
        for i, status in enumerate(statuses):
            louver = Louver(i + 1)
            assert self.mtdome_com is not None
            if louver in self.mtdome_com.louvers_enabled:
                translated_status = self._translate_motion_state_if_necessary(status)
            else:
                translated_status = MotionState.DISABLED
            motion_state.append(translated_status)
            in_position.append(
                translated_status
                in [
                    MotionState.STOPPED,
                    MotionState.STOPPED_BRAKED,
                    MotionState.CLOSED,
                    MotionState.OPEN,
                    MotionState.DISABLED,
                ]
            )
            brake_index = Brake[f"LOUVER_{louver.name}"]
            await self.set_brakes_engaged_bit(translated_status, brake_index)
        await self.evt_louversMotion.set_write(state=motion_state, inPosition=in_position)
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)

    async def _check_errors_and_send_events_shutter(self, llc_status: dict[str, typing.Any]) -> None:
        """Check errors and send events for the aperture shutter.

        Parameters
        ----------
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if self.apscs_state != llc_status["status"]:
            self.apscs_state = llc_status["status"]
            self.log.debug(f"ApSCS state now is {self.apscs_state}")
        if len(messages) != 1 or codes[0] != 0:
            fault_code = ", ".join([f"{message['code']}={message['description']}" for message in messages])
            await self.evt_shutterEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
        else:
            await self.evt_shutterEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        statuses = llc_status["status"]
        motion_state: list[str] = []
        in_position: list[bool] = []

        # The number of statuses has been validated by the JSON schema. So
        # here it is safe to loop over all statuses.
        for index, status in enumerate(statuses):
            translated_status = self._translate_motion_state_if_necessary(status)
            motion_state.append(translated_status)
            in_position.append(
                translated_status
                in [
                    MotionState.STOPPED,
                    MotionState.STOPPED_BRAKED,
                    MotionState.CLOSED,
                    MotionState.OPEN,
                ]
            )
            if index == 0:
                brake_index = Brake.APSCS_LEFT_DOOR
            else:
                brake_index = Brake.APSCS_RIGHT_DOOR
            await self.set_brakes_engaged_bit(translated_status, brake_index)
        await self.evt_shutterMotion.set_write(state=motion_state, inPosition=in_position)
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)

    async def _check_errors_and_send_events_rad(self, llc_status: dict[str, typing.Any]) -> None:
        """Check errors and send events for the rear access door.

        Parameters
        ----------
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if self.rad_state != llc_status["status"]:
            self.rad_state = llc_status["status"]
            self.log.debug(f"RAD state now is {self.rad_state}")
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            if len(messages) != 1 or codes[0] != 0:
                fault_code = ", ".join(
                    [f"{message['code']}={message['description']}" for message in messages]
                )
                await self.evt_radEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
            else:
                await self.evt_radEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        statuses = llc_status["status"]
        motion_state: list[str] = []
        in_position: list[bool] = []

        # The number of statuses has been validated by the JSON schema. So
        # here it is safe to loop over all statuses.
        for index, status in enumerate(statuses):
            translated_status = self._translate_motion_state_if_necessary(status)
            motion_state.append(translated_status)
            in_position.append(
                translated_status
                in [
                    MotionState.STOPPED,
                    MotionState.STOPPED_BRAKED,
                    MotionState.CLOSED,
                    MotionState.OPEN,
                ]
            )
            if index == 0:
                brake_index = Brake.RAD_LEFT_DOOR
            else:
                brake_index = Brake.RAD_RIGHT_DOOR
            await self.set_brakes_engaged_bit(translated_status, brake_index)

        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_radMotion.set_write(state=motion_state, inPosition=in_position)
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)

    async def _check_errors_and_send_events_calibration_screen(
        self, llc_status: dict[str, typing.Any]
    ) -> None:
        """Check errors and send events for the calibration screen.

        Parameters
        ----------
        llc_status : `dict` [`str`, `typing.Any`]
            The status containing errors and event information.
        """
        messages = llc_status["messages"]
        codes = [message["code"] for message in messages]
        if self.cscs_state != llc_status["status"]:
            self.cscs_state = llc_status["status"]
            self.log.debug(f"Calibration Screen state now is {self.cscs_state}")
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            if len(messages) != 1 or codes[0] != 0:
                fault_code = ", ".join(
                    [f"{message['code']}={message['description']}" for message in messages]
                )
                await self.evt_calibrationScreenEnabled.set_write(
                    state=EnabledState.FAULT, faultCode=fault_code
                )
            else:
                await self.evt_calibrationScreenEnabled.set_write(state=EnabledState.ENABLED, faultCode="")

        motion_state = self._translate_motion_state_if_necessary(llc_status["status"])
        in_position = False
        if motion_state in [
            MotionState.STOPPED,
            MotionState.STOPPED_BRAKED,
        ]:
            in_position = True

        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_calibrationScreenMotion.set_write(state=motion_state, inPosition=in_position)
        await self.set_brakes_engaged_bit(motion_state, Brake.CSCS.value)
        # TODO OSW-1491 Remove backward compatibility with XML 24.3
        if XML_VERSION == TWENTYFOUR_FOUR:
            await self.evt_brakesEngaged.set_write(brakes=str(self.brakes_engaged_bitmask))
        else:
            await self.evt_brakesEngaged.set_write(brakes=self.brakes_engaged_bitmask)

    def _translate_motion_state_if_necessary(self, state: str) -> MotionState:
        try:
            motion_state = MotionState[state]
        except KeyError:
            motion_state = motion_state_translations[state]
        return motion_state

    async def close_tasks(self) -> None:
        """Disconnect from the TCP/IP controller, if connected, and stop
        the mock controller, if running.
        """
        await super().close_tasks()
        await self.disconnect()

    async def configure(self, config: SimpleNamespace) -> None:
        self.config = config

    async def call_method(self, method: typing.Callable, **kwargs: typing.Any) -> typing.Any:
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
            assert self.mtdome_com is not None
            response_code = self.mtdome_com.communication_error_report["response_code"]
            if response_code in [
                mtdomecom.ResponseCode.ROTATING_PART_NOT_RECEIVED,
                mtdomecom.ResponseCode.ROTATING_PART_NOT_REPLIED,
            ]:
                await self._handle_command_exception(self.mtdome_com.communication_error_report)
                return None
            else:
                raise
        except Exception:
            name = getattr(method, "__name__", repr(method))
            await self.go_fault(name)
            return None

    async def _handle_command_exception(self, communication_error_report: dict[str, typing.Any]) -> None:
        """Handle reports for communication errors.

        Parameters
        ----------
        communication_error_report : `dict` [`str`, `typing.Any`]
            The error report to handle.
        """
        command_name = communication_error_report["command_name"]
        exception = communication_error_report["exception"]
        response_code = communication_error_report["response_code"]
        tb = traceback.format_exception(exception)
        fault_code = f"{response_code.name}: " + "".join(tb)
        self.log.debug(f"{command_name=}, {fault_code=}")
        if isinstance(exception, (TimeoutError, ConnectionError, EOFError)):
            await self.go_fault(command_name)
        elif command_name in mtdomecom.EL_COMMANDS:
            await self.evt_elEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
        elif command_name in mtdomecom.SHUTTER_COMMANDS:
            await self.evt_shutterEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
        elif command_name in mtdomecom.LOUVERS_COMMANDS:
            await self.evt_louversEnabled.set_write(state=EnabledState.FAULT, faultCode=fault_code)
        else:
            self.log.error(fault_code)

    async def go_fault(self, method: str) -> None:
        """Convenience method to go to FAULT state.

        Parameters
        ----------
        method : `str`
            The name of the method that causes the FAULT state.
        """
        if self.mtdome_com is not None:
            await self.mtdome_com.disconnect()
        else:
            self.log.exception(f"{self.mtdome_com=}: Cannot stop periodic tasks.")
        await self.fault(code=None, report=f"Error calling {method=}.")

    async def set_brakes_engaged_bit(self, motion_state: MotionState, index: int) -> None:
        """Set a bit on the brakes engaged bitmask.

        Parameters
        ----------
        motion_state : `MotionState`
            The motion state to determine the bit value with.
        index : `int`
            The bit index to update.
        """
        if motion_state in BRAKES_ENGAGED_STATES:
            self.brakes_engaged_bitmask = self.brakes_engaged_bitmask | (1 << index)
        else:
            self.brakes_engaged_bitmask = self.brakes_engaged_bitmask & ~(1 << index)

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

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

import asyncio
import contextlib
import logging
import math
import pathlib
import typing
import unittest

import numpy as np
import pytest
import yaml
from lsst.ts import mtdome, mtdomecom, salobj, tcpip, utils
from lsst.ts.xml.enums.MTDome import (
    EnabledState,
    MotionState,
    OnOff,
    OperationalMode,
    PowerManagementMode,
    SubSystemId,
)

STD_TIMEOUT = 10  # standard command and event timeout (sec)
SHORT_TIMEOUT = 1  # short command and event timeout (sec)

CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def basic_make_csc(
        self,
        initial_state: salobj.State,
        config_dir: str,
        simulation_mode: int,
        override: str = "",
        **kwargs: typing.Any,
    ) -> None:
        # Disable all periodic tasks so the unit tests can take full control.
        return mtdome.MTDomeCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            override=override,
            start_periodic_tasks=False,
        )

    @contextlib.asynccontextmanager
    async def create_mock_controller(
        self,
        port: int,
        include_command_id: bool = True,
    ) -> typing.AsyncGenerator[tcpip.BaseClientOrServer, None]:
        mock_ctrl = mtdomecom.MockMTDomeController(
            port=port,
            log=logging.getLogger("CscTestCase"),
        )
        mock_ctrl.determine_current_tai = self.determine_current_tai
        await asyncio.wait_for(mock_ctrl.start_task, timeout=STD_TIMEOUT)
        yield mock_ctrl
        await mock_ctrl.close()

    async def test_standard_state_transitions(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.check_standard_state_transitions(
                enabled_commands=(
                    mtdomecom.CommandName.MOVE_AZ,
                    mtdomecom.CommandName.MOVE_EL,
                    mtdomecom.CommandName.STOP_AZ,
                    mtdomecom.CommandName.STOP_EL,
                    "stop",
                    mtdomecom.CommandName.CRAWL_AZ,
                    mtdomecom.CommandName.CRAWL_EL,
                    mtdomecom.CommandName.SET_LOUVERS,
                    mtdomecom.CommandName.CLOSE_LOUVERS,
                    mtdomecom.CommandName.STOP_LOUVERS,
                    mtdomecom.CommandName.OPEN_SHUTTER,
                    mtdomecom.CommandName.CLOSE_SHUTTER,
                    mtdomecom.CommandName.STOP_SHUTTER,
                    mtdomecom.CommandName.PARK,
                    "goStationary",
                    mtdomecom.CommandName.GO_STATIONARY_AZ,
                    mtdomecom.CommandName.GO_STATIONARY_EL,
                    mtdomecom.CommandName.GO_STATIONARY_LOUVERS,
                    mtdomecom.CommandName.GO_STATIONARY_SHUTTER,
                    mtdomecom.CommandName.SET_TEMPERATURE,
                    mtdomecom.CommandName.FANS,
                    mtdomecom.CommandName.INFLATE,
                    mtdomecom.CommandName.EXIT_FAULT,
                    "home",
                    mtdomecom.CommandName.SET_ZERO_AZ,
                    mtdomecom.CommandName.RESET_DRIVES_AZ,
                    mtdomecom.CommandName.RESET_DRIVES_SHUTTER,
                    "setOperationalMode",
                    mtdomecom.CommandName.SET_POWER_MANAGEMENT_MODE,
                ),
            )

    async def test_version(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=mtdome.__version__,
                subsystemVersions="",
            )

    async def determine_current_tai(self) -> None:
        # Deliberately left empty.
        pass

    async def set_csc_to_enabled(self) -> None:
        await salobj.set_summary_state(remote=self.remote, state=salobj.State.ENABLED)
        await self.assert_next_sample(
            topic=self.remote.evt_azEnabled, state=EnabledState.ENABLED
        )
        await self.assert_next_sample(
            topic=self.remote.evt_elEnabled, state=EnabledState.ENABLED
        )
        await self.assert_next_sample(
            topic=self.remote.evt_shutterEnabled, state=EnabledState.ENABLED
        )
        await self.assert_next_sample(topic=self.remote.evt_brakesEngaged, brakes=0)
        await self.assert_next_sample(topic=self.remote.evt_interlocks, interlocks=0)
        await self.assert_next_sample(
            topic=self.remote.evt_lockingPinsEngaged, engaged=0
        )

        self.csc.mtdome_com.mock_ctrl.determine_current_tai = self.determine_current_tai
        sub_system_ids = (
            SubSystemId.AMCS
            | SubSystemId.LWSCS
            | SubSystemId.APSCS
            | SubSystemId.LCS
            | SubSystemId.THCS
            | SubSystemId.MONCS
            | SubSystemId.RAD
            | SubSystemId.CSCS
            | SubSystemId.CBCS
        )
        await self.validate_operational_mode(
            operational_mode=OperationalMode.NORMAL, sub_system_ids=sub_system_ids
        )
        await self.assert_next_sample(topic=self.remote.evt_azConfigurationApplied)

    async def assert_command_replied(self, cmd: str) -> None:
        """Assert that the specified command has been replied to.

        The `commands_without_reply` dict contains (commandId, command) pairs
        for which a command has been sent but hasn't been replied to yet. Call
        this method after receiving a reply to ensure that the (commandId,
        command) pair has been removed from the dict, indicating that it has
        been replied to with the correct commandId.

        In general, it is unwise to use this method with any of the status
        commands, since the CSC sends those in a loop and at any given time
        such a command is likely to have been issued by that loop.

        Parameters
        ----------
        cmd : `str`
            The command that should have been replied to.
        """
        assert (
            len(
                [
                    key
                    for key in self.csc.mtdome_com.commands_without_reply
                    if self.csc.mtdome_com.commands_without_reply[key].command == cmd
                ]
            )
            == 0
        )

    async def test_do_moveAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            desired_position = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
            data = await self.assert_next_sample(
                topic=self.remote.evt_azTarget, position=desired_position
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_AZ)
            assert math.isclose(desired_velocity, data.velocity, abs_tol=1e-7)

            # Give some time to the mock device to move.
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )

            # Now also check the azMotion event.
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.MOVING.name
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )

    async def test_do_moveEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mtdome_com.mock_ctrl.lwscs.command_time_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai
            )

            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            desired_position = 40
            await self.remote.cmd_moveEl.set_start(
                position=desired_position, timeout=STD_TIMEOUT
            )
            await self.assert_next_sample(
                topic=self.remote.evt_elTarget, position=desired_position, velocity=0
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_EL)

            # Now also check the elMotion event.
            await self.csc.mtdome_com.status_lwscs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.LWSCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.MOVING.name
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )

    async def test_do_stopAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            # First the AMCS needs to be moving before it can be stopped.
            desired_position = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name

            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_AZ)

            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.AMCS
            )

            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )
            await self.assert_command_replied(cmd="stop")

    async def test_do_stopEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.LWSCS
            )

            # First the AMCS needs to be moving before it can be stopped.
            desired_position = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )

            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_EL)

    async def test_do_stop(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            # First the AMCS needs to be moving before it can be stopped.
            desired_position = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name
            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_AZ)

            sub_system_ids = (
                SubSystemId.AMCS
                | SubSystemId.LWSCS
                | SubSystemId.APSCS
                | SubSystemId.LCS
                | SubSystemId.THCS
                | SubSystemId.MONCS
            )
            await self.remote.cmd_stop.set_start(
                engageBrakes=False,
                subSystemIds=sub_system_ids,
            )

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )
            await self.assert_command_replied(cmd="stop")

            await self.csc.mtdome_com.status_lwscs()
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

    async def test_do_crawlAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            desired_velocity = 0.1
            await self.remote.cmd_crawlAz.set_start(
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
            data = await self.assert_next_sample(
                topic=self.remote.evt_azTarget,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.CRAWL_AZ)
            assert np.isnan(data.position)
            assert math.isclose(desired_velocity, data.velocity, abs_tol=1e-7)

            # Give some time to the mock device to move.
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )

            # Now also check the azMotion event.
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.CRAWLING.name
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.CRAWLING,
                inPosition=True,
            )

    async def test_do_crawlEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = 1000
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mtdome_com.mock_ctrl.lwscs.command_time_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai
            )

            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            desired_velocity = 0.1
            await self.remote.cmd_crawlEl.set_start(
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            data = await self.assert_next_sample(
                topic=self.remote.evt_elTarget,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.CRAWL_EL)
            assert np.isnan(data.position)
            assert math.isclose(desired_velocity, data.velocity, abs_tol=1e-7)

            # Now also check the elMotion event.
            await self.csc.mtdome_com.status_lwscs()
            lwscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.LWSCS.value
            ]
            assert lwscs_status["status"]["status"] == MotionState.CRAWLING.name
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.CRAWLING,
                inPosition=True,
            )

    async def test_do_setLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            louver_id = 5
            target_position = 100
            desired_position = np.full(mtdomecom.LCS_NUM_LOUVERS, -1.0, dtype=float)
            desired_position[louver_id] = target_position
            await self.remote.cmd_setLouvers.set_start(
                position=desired_position.tolist(),
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.SET_LOUVERS)

    async def test_do_closeLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeLouvers.set_start()
            await self.assert_command_replied(cmd=mtdomecom.CommandName.CLOSE_LOUVERS)

    async def test_do_stopLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.LCS
            )

    async def test_do_openShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = 1000

            await self.remote.cmd_openShutter.set_start()
            await self.assert_command_replied(cmd=mtdomecom.CommandName.OPEN_SHUTTER)

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            await self.csc.mtdome_com.status_apscs()
            apscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert apscs_status["status"]["status"] == [
                MotionState.LP_DISENGAGING.name,
                MotionState.LP_DISENGAGING.name,
            ]

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 10.1
            )
            self.csc.mtdome_com.mock_ctrl.apscs.current_state = [
                MotionState.OPENING.name
            ] * mtdomecom.APSCS_NUM_SHUTTERS
            await self.csc.mtdome_com.status_apscs()
            apscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert apscs_status["status"]["status"] == [
                MotionState.PROXIMITY_OPEN_LS_ENGAGED.name,
                MotionState.PROXIMITY_OPEN_LS_ENGAGED.name,
            ]

    async def test_do_closeShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):

            await self.set_csc_to_enabled()

            start_tai = 1000

            self.csc.mtdome_com.mock_ctrl.apscs.position_actual = np.full(
                mtdomecom.APSCS_NUM_SHUTTERS, 100.0, dtype=float
            )
            self.csc.mtdome_com.mock_ctrl.apscs.start_state = [
                MotionState.OPEN.name,
                MotionState.OPEN.name,
            ]
            self.csc.mtdome_com.mock_ctrl.apscs.current_state = [
                MotionState.OPEN.name,
                MotionState.OPEN.name,
            ]
            self.csc.mtdome_com.mock_ctrl.apscs.target_state = [
                MotionState.OPEN.name,
                MotionState.OPEN.name,
            ]

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = start_tai

            await self.remote.cmd_closeShutter.set_start()
            await self.assert_command_replied(cmd=mtdomecom.CommandName.CLOSE_SHUTTER)

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            await self.csc.mtdome_com.status_apscs()
            apscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert apscs_status["status"]["status"] == [
                MotionState.LP_DISENGAGING.name,
                MotionState.LP_DISENGAGING.name,
            ]

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 10.1
            )
            self.csc.mtdome_com.mock_ctrl.apscs.current_state = [
                MotionState.OPENING.name
            ] * mtdomecom.APSCS_NUM_SHUTTERS
            await self.csc.mtdome_com.status_apscs()
            apscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert apscs_status["status"]["status"] == [
                MotionState.PROXIMITY_CLOSED_LS_ENGAGED.name,
                MotionState.PROXIMITY_CLOSED_LS_ENGAGED.name,
            ]
            telemetry = await self.assert_next_sample(
                topic=self.remote.tel_apertureShutter
            )
            assert math.isclose(telemetry.positionActual[0], 0.0)
            assert math.isclose(telemetry.positionActual[1], 0.0)
            # Assert there are no -0.0 values.
            assert math.copysign(1, telemetry.positionActual[0]) > 0
            assert math.copysign(1, telemetry.positionActual[1]) > 0

    async def test_do_stopShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.APSCS
            )
            await self.assert_command_replied(cmd="stop")

    async def test_do_park(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            # This event gets emitted as soon as the CSC has started.
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            await self.remote.cmd_park.set_start()
            await self.assert_next_sample(
                topic=self.remote.evt_azTarget,
                position=360.0 - mtdomecom.DOME_AZIMUTH_OFFSET,
                velocity=0,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.PARK)

            # No new azMotion event gets emitted since the PARKED event already
            # was emitted and AMCS has not changed status since, so we're done.

    async def test_do_stop_and_brake(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            # First the AMCS needs to be moving before it can be stopped.
            desired_position = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_AZ)

            sub_system_ids = (
                SubSystemId.AMCS
                | SubSystemId.LWSCS
                | SubSystemId.APSCS
                | SubSystemId.LCS
                | SubSystemId.THCS
                | SubSystemId.MONCS
            )
            await self.remote.cmd_stop.set_start(
                engageBrakes=True,
                subSystemIds=sub_system_ids,
            )

            # Give some time to the mock device to move.
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            await self.assert_command_replied(cmd="stop")

            # Now also check the azMotion event.
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

    async def test_do_setTemperature(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            desired_temperature = 10.0
            await self.remote.cmd_setTemperature.set_start(
                temperature=desired_temperature,
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.SET_TEMPERATURE)

    async def test_config(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # All values are below the limits.
            system = mtdomecom.LlcName.AMCS
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
                {"target": "vmax", "setting": [1.0]},
            ]
            await self.csc.mtdome_com.config_llcs(system, settings)

            # The value of AMCS amax is too high.
            system = mtdomecom.LlcName.AMCS
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [1.0]},
                {"target": "vmax", "setting": [1.0]},
            ]
            with pytest.raises(ValueError):
                await self.csc.mtdome_com.config_llcs(system, settings)

            # The value of AMCS amax is too low.
            system = mtdomecom.LlcName.AMCS
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [-0.5]},
                {"target": "vmax", "setting": [1.0]},
            ]
            with pytest.raises(ValueError):
                await self.csc.mtdome_com.config_llcs(system, settings)

            # The param AMCS smax doesn't exist.
            system = mtdomecom.LlcName.AMCS
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
                {"target": "vmax", "setting": [1.0]},
                {"target": "smax", "setting": [1.0]},
            ]
            with pytest.raises(KeyError):
                await self.csc.mtdome_com.config_llcs(system, settings)

            # No parameter can be missing.
            system = mtdomecom.LlcName.AMCS
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
            ]
            with pytest.raises(KeyError):
                await self.csc.mtdome_com.config_llcs(system, settings)

    async def validate_configuration_values(self, config_file: str) -> None:
        if config_file == "_init.yaml":
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
        else:
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED, override=config_file
            )

        config_jmax = math.degrees(self.csc.mtdome_com.mock_ctrl.amcs.jmax)
        config_amax = math.degrees(self.csc.mtdome_com.mock_ctrl.amcs.amax)
        config_vmax = math.degrees(self.csc.mtdome_com.mock_ctrl.amcs.vmax)

        await self.csc.mtdome_com.status_amcs()
        data = await self.assert_next_sample(
            topic=self.remote.evt_azConfigurationApplied
        )
        with open(CONFIG_DIR / config_file) as config_file:  # type: ignore
            config_data = yaml.safe_load(config_file)
            if (
                config_data["amcs_vmax"] == -1
                or config_data["amcs_amax"] == -1
                or config_data["amcs_jmax"] == -1
            ):
                expected_jmax = math.degrees(mtdomecom.AMCS_JMAX)
                expected_amax = math.degrees(mtdomecom.AMCS_AMAX)
                expected_vmax = math.degrees(mtdomecom.AMCS_VMAX)
            else:
                expected_jmax = config_data["amcs_jmax"]
                expected_amax = config_data["amcs_amax"]
                expected_vmax = config_data["amcs_vmax"]

            assert config_jmax == pytest.approx(expected_jmax)
            assert config_amax == pytest.approx(expected_amax)
            assert config_vmax == pytest.approx(expected_vmax)

            if data.jmax != pytest.approx(expected_jmax):
                # Due to the status task, the azConfigurationApplied event can
                # be sent before the config values have been applied. In that
                # case a second azConfigurationApplied event will be emitted.
                data = await self.assert_next_sample(
                    topic=self.remote.evt_azConfigurationApplied
                )
            assert data.jmax == pytest.approx(expected_jmax)
            assert data.amax == pytest.approx(expected_amax)
            assert data.vmax == pytest.approx(expected_vmax)

        await salobj.set_summary_state(remote=self.remote, state=salobj.State.STANDBY)

    async def test_configure(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.validate_configuration_values(config_file="_init.yaml")
            await self.validate_configuration_values(
                config_file="config_for_friction_drive_system.yaml"
            )
            await self.validate_configuration_values(
                config_file="config_for_friction_drive_system_with_four_motors.yaml"
            )

    async def test_do_fans(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mtdome_com.mock_ctrl.amcs.command_time_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai
            )

            await self.csc.mtdome_com.write_then_read_reply(
                command=mtdomecom.CommandName.FANS, speed=50.0
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.FANS)

            # Give some time to the mock device to move.
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )

            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["fans"] == pytest.approx(50.0)

    async def test_do_inflate(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mtdome_com.mock_ctrl.amcs.command_time_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai
            )

            await self.csc.mtdome_com.write_then_read_reply(
                command=mtdomecom.CommandName.INFLATE, action=OnOff.ON.value
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.INFLATE)

            # Give some time to the mock device to move.
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )

            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["inflate"] == OnOff.ON.value

    async def test_status(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            # It should be possible to always execute the status command but
            # the connection with the lower level components only gets made in
            # DISABLED and ENABLED state so that's why the state gets set to
            # ENABLED here.
            await self.set_csc_to_enabled()

            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert math.isclose(amcs_status["positionActual"], 328.0)
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            await self.csc.mtdome_com.status_apscs()
            apscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert apscs_status["status"]["status"] == [
                MotionState.CLOSED.name,
                MotionState.CLOSED.name,
            ]
            assert apscs_status["positionActual"] == [0.0, 0.0]

            await self.csc.mtdome_com.status_lcs()
            lcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.LCS.value
            ]
            assert (
                lcs_status["status"]["status"]
                == [mtdomecom.InternalMotionState.STATIONARY.name]
                * mtdomecom.LCS_NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdomecom.LCS_NUM_LOUVERS

            await self.csc.mtdome_com.status_lwscs()
            lwscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.LWSCS.value
            ]
            assert lwscs_status["status"]["status"] == MotionState.STOPPED.name
            assert lwscs_status["positionActual"] == 0
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            await self.csc.mtdome_com.status_moncs()
            moncs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.MONCS.value
            ]
            assert moncs_status["status"]["status"] == MotionState.CLOSED.name
            assert moncs_status["data"] == [0.0] * mtdomecom.MON_NUM_SENSORS

            await self.csc.mtdome_com.status_thcs()
            thcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.THCS.value
            ]
            assert thcs_status["status"]["status"] == MotionState.DISABLED.name
            assert thcs_status["temperature"] == [0.0] * mtdomecom.THCS_NUM_SENSORS

            await self.csc.mtdome_com.status_rad()
            rad_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.RAD.value
            ]
            assert (
                rad_status["status"]["status"]
                == [MotionState.CLOSED.name] * mtdomecom.RAD_NUM_DOORS
            )
            assert rad_status["positionActual"] == [0.0] * mtdomecom.RAD_NUM_DOORS

            await self.csc.mtdome_com.status_cbcs()
            cbcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.CBCS.value
            ]
            assert (
                cbcs_status["fuseIntervention"]
                == [False] * mtdomecom.CBCS_NUM_CAPACITOR_BANKS
            )
            assert (
                cbcs_status["smokeDetected"]
                == [False] * mtdomecom.CBCS_NUM_CAPACITOR_BANKS
            )
            assert (
                cbcs_status["highTemperature"]
                == [False] * mtdomecom.CBCS_NUM_CAPACITOR_BANKS
            )
            assert (
                cbcs_status["lowResidualVoltage"]
                == [False] * mtdomecom.CBCS_NUM_CAPACITOR_BANKS
            )
            assert (
                cbcs_status["doorOpen"] == [False] * mtdomecom.CBCS_NUM_CAPACITOR_BANKS
            )

    async def test_status_error(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Introduce error messages. This will be improved once error codes
            # have been specified in a future Dome Software meeting.
            expected_messages = [
                {"code": 100, "description": "Drive 1 temperature too high"},
                {"code": 100, "description": "Drive 2 temperature too high"},
            ]
            expected_fault_code = ", ".join(
                [
                    f"{message['code']}={message['description']}"
                    for message in expected_messages
                ]
            )
            self.csc.mtdome_com.mock_ctrl.amcs.messages = expected_messages
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["messages"] == expected_messages
            assert math.isclose(amcs_status["positionActual"], 328.0)
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled,
                state=EnabledState.FAULT,
                faultCode=expected_fault_code,
            )

    async def test_exitFault(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            # First the AMCS needs to be moving before it can be stopped.
            desired_position = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_AZ)

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name

            await self.csc.mtdome_com.status_amcs()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
            )

            # Prepare the lower level components
            current_tai = self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            az_drives_in_error = [1, 1, 0, 0, 0]
            await self.csc.mtdome_com.mock_ctrl.amcs.set_fault(
                current_tai, az_drives_in_error
            )
            aps_drives_in_error = [1, 1, 0, 0]
            await self.csc.mtdome_com.mock_ctrl.apscs.set_fault(
                current_tai, aps_drives_in_error
            )
            self.csc.mtdome_com.mock_ctrl.amcs._commanded_motion_state = (
                MotionState.ERROR
            )

            # Make sure that the Enabled events are sent.
            await self.csc.mtdome_com.status_amcs()
            await self.csc.mtdome_com.status_apscs()
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled, state=EnabledState.FAULT
            )
            await self.assert_next_sample(
                topic=self.remote.evt_shutterEnabled, state=EnabledState.FAULT
            )

            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.ERROR.name

            await self.remote.cmd_exitFault.set_start(
                subSystemIds=SubSystemId.AMCS | SubSystemId.APSCS
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.EXIT_FAULT_AZ)
            await self.assert_command_replied(
                cmd=mtdomecom.CommandName.EXIT_FAULT_SHUTTER
            )

            az_reset = [1, 1, 0, 0, 0]
            await self.remote.cmd_resetDrivesAz.set_start(reset=az_reset)
            await self.assert_command_replied(cmd=mtdomecom.CommandName.RESET_DRIVES_AZ)
            aps_reset = [1, 1, 0, 0]
            await self.remote.cmd_resetDrivesShutter.set_start(reset=aps_reset)
            await self.assert_command_replied(
                cmd=mtdomecom.CommandName.RESET_DRIVES_SHUTTER
            )
            await self.remote.cmd_exitFault.set_start(
                subSystemIds=SubSystemId.AMCS
                | SubSystemId.APSCS
                | SubSystemId.LWSCS
                | SubSystemId.MONCS
                | SubSystemId.LCS
                | SubSystemId.THCS
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.EXIT_FAULT_AZ)
            await self.assert_command_replied(
                cmd=mtdomecom.CommandName.EXIT_FAULT_SHUTTER
            )

            # Make sure that the Enabled events are sent.
            await self.csc.mtdome_com.status_amcs()
            await self.csc.mtdome_com.status_apscs()
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled, state=EnabledState.ENABLED
            )
            await self.assert_next_sample(
                topic=self.remote.evt_shutterEnabled, state=EnabledState.ENABLED
            )

            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert (
                amcs_status["status"]["status"]
                == mtdomecom.InternalMotionState.STATIONARY.name
            )

            await self.csc.mtdome_com.status_apscs()
            apscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert apscs_status["status"]["status"] == [
                mtdomecom.InternalMotionState.STATIONARY.name,
                mtdomecom.InternalMotionState.STATIONARY.name,
            ]
            assert math.isclose(apscs_status["positionActual"][0], 0.0, abs_tol=0.001)
            assert math.isclose(apscs_status["positionActual"][1], 0.0, abs_tol=0.001)

            await self.csc.mtdome_com.status_lcs()
            lcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.LCS.value
            ]
            assert (
                lcs_status["status"]["status"]
                == [mtdomecom.InternalMotionState.STATIONARY.name]
                * mtdomecom.LCS_NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdomecom.LCS_NUM_LOUVERS

            await self.csc.mtdome_com.status_lwscs()
            lwscs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.LWSCS.value
            ]
            assert (
                lwscs_status["status"]["status"]
                == mtdomecom.InternalMotionState.STATIONARY.name
            )
            assert lwscs_status["positionActual"] == 0

            await self.csc.mtdome_com.status_moncs()
            moncs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.MONCS.value
            ]
            assert moncs_status["status"]["status"] == MotionState.CLOSED.name
            assert moncs_status["data"] == [0.0] * mtdomecom.MON_NUM_SENSORS

            await self.csc.mtdome_com.status_thcs()
            thcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.THCS.value
            ]
            assert (
                thcs_status["status"]["status"]
                == mtdomecom.InternalMotionState.STATIONARY.name
            )
            assert thcs_status["temperature"] == [0.0] * mtdomecom.THCS_NUM_SENSORS

    async def test_setZeroAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            # Compensate for the dome azimuth offset.
            desired_position = utils.angle_wrap_nonnegative(
                2.0 - mtdomecom.DOME_AZIMUTH_OFFSET
            ).degree
            desired_velocity = 0.0
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdomecom.CommandName.MOVE_AZ)
            data = await self.assert_next_sample(
                topic=self.remote.evt_azTarget, position=desired_position
            )
            assert math.isclose(desired_velocity, data.velocity, abs_tol=1e-7)

            # Give some time to the mock device to move.
            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            self.csc.mtdome_com.mock_ctrl.amcs.current_state = MotionState.MOVING.name

            # Now also check the azMotion event.
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["status"]["status"] == MotionState.MOVING.name

            # Cannot set to zero while AMCS is MOVING
            with salobj.assertRaisesAckError():
                await self.remote.cmd_setZeroAz.set_start()
                # await self.assert_command_replied(cmd="setZeroAz")

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 2.0
            )
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["positionActual"] == pytest.approx(330.0)
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

            await self.remote.cmd_setZeroAz.set_start()
            await self.assert_command_replied(cmd="setZeroAz")

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            await self.csc.mtdome_com.status_amcs()
            amcs_status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.AMCS.value
            ]
            assert amcs_status["positionActual"] == pytest.approx(328.0)
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

    async def test_homeShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            initial_position_actual = np.full(
                mtdomecom.APSCS_NUM_SHUTTERS, 0.0, dtype=float
            )
            self.csc.mtdome_com.mock_ctrl.apscs.position_actual = (
                initial_position_actual
            )

            # Set the TAI time in the mock controller for easier control
            self.csc.mtdome_com.mock_ctrl.current_tai = utils.current_tai()

            await self.csc.mtdome_com.status_apscs()
            status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert status["positionActual"] == initial_position_actual.tolist()

            sub_system_ids = SubSystemId.APSCS
            await self.remote.cmd_home.set_start(subSystemIds=sub_system_ids)
            await self.assert_command_replied(cmd="home")

            self.csc.mtdome_com.mock_ctrl.current_tai = (
                self.csc.mtdome_com.mock_ctrl.current_tai + 0.1
            )
            await self.csc.mtdome_com.status_apscs()
            status = self.csc.mtdome_com.lower_level_status[
                mtdomecom.LlcName.APSCS.value
            ]
            assert (
                status["positionActual"]
                == np.zeros(mtdomecom.APSCS_NUM_SHUTTERS, dtype=float).tolist()
            )

    async def validate_operational_mode(
        self, operational_mode: OperationalMode, sub_system_ids: int
    ) -> None:
        await self.assert_command_replied(cmd="setOperationalMove")

        # Dictionary to look up which status telemetry function to call for
        # which sub_system.
        status_dict = {
            SubSystemId.AMCS: self.csc.mtdome_com.status_amcs,
            SubSystemId.APSCS: self.csc.mtdome_com.status_apscs,
            SubSystemId.CBCS: self.csc.mtdome_com.status_cbcs,
            SubSystemId.CSCS: self.csc.mtdome_com.status_cscs,
            SubSystemId.LCS: self.csc.mtdome_com.status_lcs,
            SubSystemId.LWSCS: self.csc.mtdome_com.status_lwscs,
            SubSystemId.MONCS: self.csc.mtdome_com.status_moncs,
            SubSystemId.RAD: self.csc.mtdome_com.status_rad,
            SubSystemId.THCS: self.csc.mtdome_com.status_thcs,
        }
        events_to_check = set()
        for sub_system_id in SubSystemId:
            if sub_system_id & sub_system_ids:
                func = status_dict[sub_system_id]
                name = mtdomecom.LlcNameDict[sub_system_id]
                await func()
                status = self.csc.mtdome_com.lower_level_status[name]
                # Not all statuses contain an operationalMode.
                if "operationalMode" in status["status"]:
                    assert status["status"]["operationalMode"] == operational_mode.name
                    events_to_check.add(sub_system_id.value)

        events_recevied = set()
        for _ in range(len(events_to_check)):
            data = await self.assert_next_sample(
                topic=self.remote.evt_operationalMode,
                timeout=STD_TIMEOUT,
            )
            assert data.operationalMode == operational_mode.value
            events_recevied.add(data.subSystemId)

        assert sorted(events_to_check) == sorted(events_recevied)

    async def test_do_setOperationalMode(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Test with one lower level component.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.AMCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            assert (
                self.csc.mtdome_com.mock_ctrl.amcs.operational_mode
                == OperationalMode.DEGRADED
            )

            # Set to NORMAL again.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            assert (
                self.csc.mtdome_com.mock_ctrl.amcs.operational_mode
                == OperationalMode.NORMAL
            )

            # Set another lower level component to degraded.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.MONCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            assert (
                self.csc.mtdome_com.mock_ctrl.moncs.operational_mode
                == OperationalMode.DEGRADED
            )

            # Set the same, first, lower level component to degraded again.
            # This should not raise an exception.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.AMCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            for llc in [
                self.csc.mtdome_com.mock_ctrl.amcs,
                self.csc.mtdome_com.mock_ctrl.moncs,
            ]:
                assert llc.operational_mode == OperationalMode.DEGRADED

            # Set two lower level components to normal.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS | SubSystemId.MONCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            for llc in [
                self.csc.mtdome_com.mock_ctrl.amcs,
                self.csc.mtdome_com.mock_ctrl.moncs,
            ]:
                assert llc.operational_mode == OperationalMode.NORMAL

            # Set two lower level components to normal again. This should not
            # raise an exception.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS | SubSystemId.MONCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            for llc in [
                self.csc.mtdome_com.mock_ctrl.amcs,
                self.csc.mtdome_com.mock_ctrl.moncs,
            ]:
                assert llc.operational_mode == OperationalMode.NORMAL

            # Set all to degraded
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = (
                SubSystemId.AMCS
                | SubSystemId.APSCS
                | SubSystemId.LCS
                | SubSystemId.LWSCS
                | SubSystemId.MONCS
                | SubSystemId.THCS
            )
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            for llc in [
                self.csc.mtdome_com.mock_ctrl.amcs,
                self.csc.mtdome_com.mock_ctrl.apscs,
                self.csc.mtdome_com.mock_ctrl.lcs,
                self.csc.mtdome_com.mock_ctrl.lwscs,
                self.csc.mtdome_com.mock_ctrl.moncs,
                self.csc.mtdome_com.mock_ctrl.thcs,
            ]:
                assert llc.operational_mode == OperationalMode.DEGRADED

            # Set all back to normal
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = (
                SubSystemId.AMCS
                | SubSystemId.APSCS
                | SubSystemId.LCS
                | SubSystemId.LWSCS
                | SubSystemId.MONCS
                | SubSystemId.THCS
            )
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            for llc in [
                self.csc.mtdome_com.mock_ctrl.amcs,
                self.csc.mtdome_com.mock_ctrl.apscs,
                self.csc.mtdome_com.mock_ctrl.lcs,
                self.csc.mtdome_com.mock_ctrl.lwscs,
                self.csc.mtdome_com.mock_ctrl.moncs,
                self.csc.mtdome_com.mock_ctrl.thcs,
            ]:
                assert llc.operational_mode == OperationalMode.NORMAL

    async def test_do_setPowerManagementMode(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            current_power_management_mode = PowerManagementMode.NO_POWER_MANAGEMENT
            await self.assert_next_sample(
                topic=self.remote.evt_powerManagementMode,
                mode=current_power_management_mode,
            )
            assert (
                self.csc.mtdome_com.power_management_mode
                == current_power_management_mode
            )

            self.csc.mtdome_com.power_management_handler.command_queue.put_nowait(
                (1, mtdomecom.CommandName.OPEN_SHUTTER)
            )
            new_power_management_mode = PowerManagementMode.OPERATIONS
            await self.remote.cmd_setPowerManagementMode.set_start(
                mode=new_power_management_mode
            )
            await self.assert_next_sample(
                topic=self.remote.evt_powerManagementMode,
                mode=new_power_management_mode,
            )
            assert (
                self.csc.mtdome_com.power_management_mode == new_power_management_mode
            )
            assert self.csc.mtdome_com.power_management_handler.command_queue.empty()

            self.csc.mtdome_com.power_management_handler.command_queue.put_nowait(
                (1, mtdomecom.CommandName.OPEN_SHUTTER)
            )
            assert (
                not self.csc.mtdome_com.power_management_handler.command_queue.empty()
            )
            await self.remote.cmd_setPowerManagementMode.set_start(
                mode=PowerManagementMode.NO_POWER_MANAGEMENT
            )
            assert self.csc.summary_state == salobj.State.ENABLED
            assert (
                not self.csc.mtdome_com.power_management_handler.command_queue.empty()
            )

    async def test_slow_network(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            self.csc.mtdome_com.mock_ctrl.enable_slow_network = True

            desired_position = 40
            desired_velocity = 0.1
            with pytest.raises(salobj.base.AckTimeoutError):
                await self.remote.cmd_moveAz.set_start(
                    position=desired_position,
                    velocity=desired_velocity,
                    timeout=STD_TIMEOUT,
                )
            data = await self.assert_next_sample(
                topic=self.remote.evt_azTarget, position=desired_position
            )
            assert math.isclose(desired_velocity, data.velocity, abs_tol=1e-7)

    @pytest.mark.skip(reason="Need to fix this.")
    async def test_network_interruption(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.assert_next_summary_state(salobj.State.STANDBY)
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            await self.assert_next_summary_state(salobj.State.DISABLED)
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.assert_next_summary_state(salobj.State.ENABLED)
            self.csc.mtdome_com.mock_ctrl.enable_network_interruption = True
            await self.assert_next_summary_state(salobj.State.FAULT)

    async def test_no_connection(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITHOUT_MOCK_CONTROLLER,
        ):
            await self.assert_next_summary_state(salobj.State.STANDBY)
            with pytest.raises(RuntimeError):
                await salobj.set_summary_state(
                    remote=self.remote, state=salobj.State.DISABLED
                )
            await self.assert_next_summary_state(salobj.State.FAULT)

    @pytest.mark.skip(reason="Need to fix this.")
    async def test_connection_lost(self) -> None:
        with open(CONFIG_DIR / "_init.yaml") as f:
            config = yaml.safe_load(f)

        async with self.create_mock_controller(
            port=config["port"]
        ) as mock_ctrl, self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdomecom.ValidSimulationMode.SIMULATION_WITHOUT_MOCK_CONTROLLER,
        ):
            await self.assert_next_summary_state(salobj.State.STANDBY)
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.DISABLED
            )
            await self.assert_next_summary_state(salobj.State.DISABLED)
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.assert_next_summary_state(salobj.State.ENABLED)

            # Now stop the MockController and verify that the CSC goes to FAULT
            # state.
            await mock_ctrl.close()
            await self.assert_next_summary_state(salobj.State.FAULT)

    async def test_bin_script(self) -> None:
        await self.check_bin_script(name="MTDome", index=None, exe_name="run_mtdome")

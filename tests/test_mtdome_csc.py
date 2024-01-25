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
from unittest import mock

import numpy as np
import pytest
import yaml
from lsst.ts import mtdome, salobj, tcpip, utils
from lsst.ts.xml.enums.MTDome import (
    EnabledState,
    MotionState,
    OnOff,
    OperationalMode,
    SubSystemId,
)

STD_TIMEOUT = 10  # standard command and event timeout (sec)
SHORT_TIMEOUT = 1  # short command and event timeout (sec)
START_MOTORS_ADD_DURATION = 5.5  # (sec)
COMMANDS_REPLIED_PERIOD = 0.2  # (sec)

CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)


# Disable all status commands to avoid overloading the CSC during unit tests.
# This means that all test cases need to request the status of the involved
# subsystem(s) themselves.
@mock.patch.dict(
    "lsst.ts.mtdome.mtdome_csc.ALL_METHODS_AND_INTERVALS",
    {"check_all_commands_have_replies": (600, True)},
)
class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def basic_make_csc(
        self,
        initial_state: salobj.State,
        config_dir: str,
        simulation_mode: int,
        override: str = "",
        **kwargs: typing.Any,
    ) -> None:
        return mtdome.MTDomeCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            override=override,
        )

    @contextlib.asynccontextmanager
    async def create_mock_controller(
        self,
        port: int,
        include_command_id: bool = True,
    ) -> typing.AsyncGenerator[tcpip.BaseClientOrServer, None]:
        mock_ctrl = mtdome.MockMTDomeController(
            port=port,
            log=logging.getLogger("CscTestCase"),
            include_command_id=include_command_id,
        )
        mock_ctrl.determine_current_tai = self.determine_current_tai
        await asyncio.wait_for(mock_ctrl.start_task, timeout=STD_TIMEOUT)
        yield mock_ctrl
        await mock_ctrl.close()

    async def test_standard_state_transitions(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.check_standard_state_transitions(
                enabled_commands=(
                    mtdome.CommandName.MOVE_AZ,
                    mtdome.CommandName.MOVE_EL,
                    mtdome.CommandName.STOP_AZ,
                    mtdome.CommandName.STOP_EL,
                    "stop",
                    mtdome.CommandName.CRAWL_AZ,
                    mtdome.CommandName.CRAWL_EL,
                    mtdome.CommandName.SET_LOUVERS,
                    mtdome.CommandName.CLOSE_LOUVERS,
                    mtdome.CommandName.STOP_LOUVERS,
                    mtdome.CommandName.OPEN_SHUTTER,
                    mtdome.CommandName.CLOSE_SHUTTER,
                    mtdome.CommandName.STOP_SHUTTER,
                    mtdome.CommandName.PARK,
                    "goStationary",
                    mtdome.CommandName.GO_STATIONARY_AZ,
                    mtdome.CommandName.GO_STATIONARY_EL,
                    mtdome.CommandName.GO_STATIONARY_LOUVERS,
                    mtdome.CommandName.GO_STATIONARY_SHUTTER,
                    mtdome.CommandName.SET_TEMPERATURE,
                    mtdome.CommandName.FANS,
                    mtdome.CommandName.INFLATE,
                    mtdome.CommandName.EXIT_FAULT,
                    "setOperationalMode",
                    mtdome.CommandName.RESET_DRIVES_AZ,
                    "setZeroAz",
                    mtdome.CommandName.RESET_DRIVES_SHUTTER,
                    "home",
                ),
            )

    async def test_version(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=mtdome.__version__,
                subsystemVersions="",
            )

    async def test_is_moveAz_same_as_current(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            # The first call always returns False since the reference position
            # and velocity are initialized to math.nan.
            assert not self.csc.is_moveAz_same_as_current(
                position=360.0 - mtdome.DOME_AZIMUTH_OFFSET, velocity=0.0
            )
            assert self.csc.is_moveAz_same_as_current(
                position=360.0 - mtdome.DOME_AZIMUTH_OFFSET, velocity=0.0
            )
            assert self.csc.is_moveAz_same_as_current(
                position=360.0 - mtdome.DOME_AZIMUTH_OFFSET - 0.2, velocity=0.0
            )
            assert self.csc.is_moveAz_same_as_current(
                position=360.0 - mtdome.DOME_AZIMUTH_OFFSET,
                velocity=mtdome.ZERO_VELOCITY_TOLERANCE / 10.0,
            )
            for position, velocity in [
                (360.0 - mtdome.DOME_AZIMUTH_OFFSET, 0.1),
                (360.0 - mtdome.DOME_AZIMUTH_OFFSET - 0.3, 0.0),
                (
                    360.0 - mtdome.DOME_AZIMUTH_OFFSET,
                    mtdome.ZERO_VELOCITY_TOLERANCE * 10.0,
                ),
                (0.0, 0.0),
                (0.0, 0.1),
            ]:
                assert not self.csc.is_moveAz_same_as_current(
                    position=position, velocity=velocity
                )

    async def determine_current_tai(self) -> None:
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
        self.csc.mock_ctrl.determine_current_tai = self.determine_current_tai
        sub_system_ids = (
            SubSystemId.AMCS
            | SubSystemId.LWSCS
            | SubSystemId.APSCS
            | SubSystemId.LCS
            | SubSystemId.THCS
            | SubSystemId.MONCS
            | SubSystemId.RAD
            | SubSystemId.CSCS
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

        In general it is unwise to use this method with any of the status
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
                    for key in self.csc.commands_without_reply
                    if self.csc.commands_without_reply[key].command == cmd
                ]
            )
            == 0
        )

    async def test_do_moveAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

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
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)
            assert desired_velocity == pytest.approx(data.velocity)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.MOVING.name
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )

    async def verify_one_moveAz_execution(self, desired_position: float) -> None:
        desired_velocity = 0.0
        await self.remote.cmd_moveAz.set_start(
            position=desired_position,
            velocity=desired_velocity,
            timeout=STD_TIMEOUT,
        )
        data = await self.assert_next_sample(
            topic=self.remote.evt_azTarget,
            position=desired_position,
            timeout=SHORT_TIMEOUT,
        )
        await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)
        assert desired_velocity == pytest.approx(data.velocity)

        # Give some time to the mock device to move.
        self.csc.mock_ctrl.current_tai = (
            self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
        )

        # Now also check the azMotion event.
        await self.csc.statusAMCS()
        amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == MotionState.MOVING.name
        await self.assert_next_sample(
            topic=self.remote.evt_azMotion,
            state=MotionState.MOVING,
            inPosition=False,
            timeout=SHORT_TIMEOUT,
        )
        for i in range(5):
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 2.0
            await asyncio.sleep(0.2)
        # The mock device should be stopped and in position now.
        await self.csc.statusAMCS()
        await self.assert_next_sample(
            topic=self.remote.evt_azMotion,
            state=MotionState.STOPPED,
            inPosition=True,
            timeout=SHORT_TIMEOUT,
        )

    async def test_do_moveAz_twice_with_zero_velocity(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
                timeout=SHORT_TIMEOUT,
            )

            await self.verify_one_moveAz_execution(desired_position=340.0)
            await self.verify_one_moveAz_execution(desired_position=0.0)

    async def test_do_moveEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.lwscs.command_time_tai = self.csc.mock_ctrl.current_tai

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
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_EL)

            # Now also check the elMotion event.
            await self.csc.statusLWSCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.LWSCS.value]
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.statusAMCS()
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

            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )

            await self.csc.statusAMCS()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)

            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.AMCS
            )

            await self.csc.statusAMCS()
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
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

            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )

            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_EL)

    async def test_do_stop(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

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

            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )
            await self.csc.statusAMCS()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)

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

            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1
            await self.csc.statusAMCS()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )
            await self.assert_command_replied(cmd="stop")

            await self.csc.statusLWSCS()
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

    async def test_do_crawlAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

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
            await self.assert_command_replied(cmd=mtdome.CommandName.CRAWL_AZ)
            assert np.isnan(data.position)
            assert desired_velocity == pytest.approx(data.velocity)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = 1000
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.lwscs.command_time_tai = self.csc.mock_ctrl.current_tai

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
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1
            data = await self.assert_next_sample(
                topic=self.remote.evt_elTarget,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.CRAWL_EL)
            assert np.isnan(data.position)
            assert desired_velocity == pytest.approx(data.velocity)

            # Now also check the elMotion event.
            await self.csc.statusLWSCS()
            lwscs_status = self.csc.lower_level_status[mtdome.LlcName.LWSCS.value]
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            louver_id = 5
            target_position = 100
            desired_position = np.full(mtdome.mock_llc.NUM_LOUVERS, -1.0, dtype=float)
            desired_position[louver_id] = target_position
            await self.remote.cmd_setLouvers.set_start(
                position=desired_position.tolist(),
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.SET_LOUVERS)

    async def test_do_closeLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeLouvers.set_start()
            await self.assert_command_replied(cmd=mtdome.CommandName.CLOSE_LOUVERS)

    async def test_do_stopLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.LCS
            )

    async def test_do_openShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_openShutter.set_start()
            await self.assert_command_replied(cmd=mtdome.CommandName.OPEN_SHUTTER)

    async def test_do_closeShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeShutter.set_start()
            await self.assert_command_replied(cmd=mtdome.CommandName.CLOSE_SHUTTER)

    async def test_do_stopShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            # This event gets emitted as soon as the CSC has started.
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            await self.remote.cmd_park.set_start()
            await self.assert_next_sample(
                topic=self.remote.evt_azTarget,
                position=360.0 - mtdome.DOME_AZIMUTH_OFFSET,
                velocity=0,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.PARK)

            # No new azMotion event gets emitted since the PARKED event already
            # was emitted and AMCS has not changed status since, so we're done.

    async def test_do_stop_and_brake(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

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

            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)

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
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1
            await self.assert_command_replied(cmd="stop")

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert (
                amcs_status["status"]["status"]
                == mtdome.InternalMotionState.STATIONARY.name
            )

    async def test_do_setTemperature(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            desired_temperature = 10.0
            await self.remote.cmd_setTemperature.set_start(
                temperature=desired_temperature,
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.SET_TEMPERATURE)

    async def test_config(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # All values are below the limits.
            system = mtdome.LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
                {"target": "vmax", "setting": [1.0]},
            ]
            await self.csc.config_llcs(system, settings)

            # The value of AMCS amax is too high.
            system = mtdome.LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [1.0]},
                {"target": "vmax", "setting": [1.0]},
            ]
            with pytest.raises(ValueError):
                await self.csc.config_llcs(system, settings)

            # The value of AMCS amax is too low.
            system = mtdome.LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [-0.5]},
                {"target": "vmax", "setting": [1.0]},
            ]
            with pytest.raises(ValueError):
                await self.csc.config_llcs(system, settings)

            # The param AMCS smax doesn't exist.
            system = mtdome.LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
                {"target": "vmax", "setting": [1.0]},
                {"target": "smax", "setting": [1.0]},
            ]
            with pytest.raises(KeyError):
                await self.csc.config_llcs(system, settings)

            # No parameter can be missing.
            system = mtdome.LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
            ]
            with pytest.raises(KeyError):
                await self.csc.config_llcs(system, settings)

    async def validate_configuration_values(self, config_file: str) -> None:
        if config_file == "_init.yaml":
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
        else:
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED, override=config_file
            )

        config_jmax = math.degrees(self.csc.mock_ctrl.amcs.jmax)
        config_amax = math.degrees(self.csc.mock_ctrl.amcs.amax)
        config_vmax = math.degrees(self.csc.mock_ctrl.amcs.vmax)

        await self.csc.statusAMCS()
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
                expected_jmax = math.degrees(
                    mtdome.llc_configuration_limits.AmcsLimits.jmax
                )
                expected_amax = math.degrees(
                    mtdome.llc_configuration_limits.AmcsLimits.amax
                )
                expected_vmax = math.degrees(
                    mtdome.llc_configuration_limits.AmcsLimits.vmax
                )
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
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
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.write_then_read_reply(
                command=mtdome.CommandName.FANS, speed=50.0
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.FANS)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["fans"] == pytest.approx(50.0)

    async def test_do_inflate(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.write_then_read_reply(
                command=mtdome.CommandName.INFLATE, action=OnOff.ON.value
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.INFLATE)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["inflate"] == OnOff.ON.value

    async def test_status(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            # It should be possible to always execute the status command but
            # the connection with the lower level components only gets made in
            # DISABLED and ENABLED state so that's why the state gets set to
            # ENABLED here.
            await self.set_csc_to_enabled()

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["positionActual"] == 0
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            await self.csc.statusApSCS()
            apscs_status = self.csc.lower_level_status[mtdome.LlcName.APSCS.value]
            assert apscs_status["status"]["status"] == [
                MotionState.STOPPED.name,
                MotionState.STOPPED.name,
            ]
            assert apscs_status["positionActual"] == [0.0, 0.0]

            await self.csc.statusLCS()
            lcs_status = self.csc.lower_level_status[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [mtdome.InternalMotionState.STATIONARY.name]
                * mtdome.mock_llc.NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS

            await self.csc.statusLWSCS()
            lwscs_status = self.csc.lower_level_status[mtdome.LlcName.LWSCS.value]
            assert lwscs_status["status"]["status"] == MotionState.STOPPED.name
            assert lwscs_status["positionActual"] == 0
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            await self.csc.statusMonCS()
            moncs_status = self.csc.lower_level_status[mtdome.LlcName.MONCS.value]
            assert moncs_status["status"]["status"] == MotionState.CLOSED.name
            assert moncs_status["data"] == [0.0] * mtdome.mock_llc.NUM_MON_SENSORS

            await self.csc.statusThCS()
            thcs_status = self.csc.lower_level_status[mtdome.LlcName.THCS.value]
            assert thcs_status["status"]["status"] == MotionState.DISABLED.name
            assert (
                thcs_status["temperature"]
                == [0.0] * mtdome.mock_llc.thcs.NUM_THERMO_SENSORS
            )

    async def test_status_error(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
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
            self.csc.mock_ctrl.amcs.messages = expected_messages
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["messages"] == expected_messages
            assert amcs_status["positionActual"] == 0
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled,
                state=EnabledState.FAULT,
                faultCode=expected_fault_code,
            )

    async def test_exitFault(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.statusAMCS()
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
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)

            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )

            await self.csc.statusAMCS()
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
            )

            # Prepare the lower level components
            current_tai = self.csc.mock_ctrl.current_tai + 0.1
            az_drives_in_error = [1, 1, 0, 0, 0]
            await self.csc.mock_ctrl.amcs.set_fault(current_tai, az_drives_in_error)
            aps_drives_in_error = [1, 1, 0, 0]
            await self.csc.mock_ctrl.apscs.set_fault(current_tai, aps_drives_in_error)
            self.csc.mock_ctrl.amcs._commanded_motion_state = MotionState.ERROR

            # Make sure that the Enabled events are sent.
            await self.csc.statusAMCS()
            await self.csc.statusApSCS()
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled, state=EnabledState.FAULT
            )
            await self.assert_next_sample(
                topic=self.remote.evt_shutterEnabled, state=EnabledState.FAULT
            )

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.ERROR.name

            # Because of backward compatibility with XML 12.0, the exitFault
            # command will also reset the AZ and ApS drives so this next
            # command will not fail.
            await self.remote.cmd_exitFault.set_start()
            await self.assert_command_replied(cmd=mtdome.CommandName.EXIT_FAULT)

            az_reset = [1, 1, 0, 0, 0]
            await self.remote.cmd_resetDrivesAz.set_start(reset=az_reset)
            await self.assert_command_replied(cmd=mtdome.CommandName.RESET_DRIVES_AZ)
            aps_reset = [1, 1, 0, 0]
            await self.remote.cmd_resetDrivesShutter.set_start(reset=aps_reset)
            await self.assert_command_replied(
                cmd=mtdome.CommandName.RESET_DRIVES_SHUTTER
            )
            await self.remote.cmd_exitFault.set_start()
            await self.assert_command_replied(cmd=mtdome.CommandName.EXIT_FAULT)

            # Make sure that the Enabled events are sent.
            await self.csc.statusAMCS()
            await self.csc.statusApSCS()
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled, state=EnabledState.ENABLED
            )
            await self.assert_next_sample(
                topic=self.remote.evt_shutterEnabled, state=EnabledState.ENABLED
            )

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert (
                amcs_status["status"]["status"]
                == mtdome.InternalMotionState.STATIONARY.name
            )

            await self.csc.statusApSCS()
            apscs_status = self.csc.lower_level_status[mtdome.LlcName.APSCS.value]
            assert apscs_status["status"]["status"] == [
                mtdome.InternalMotionState.STATIONARY.name,
                mtdome.InternalMotionState.STATIONARY.name,
            ]
            assert apscs_status["positionActual"] == [0.0, 0.0]

            await self.csc.statusLCS()
            lcs_status = self.csc.lower_level_status[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [mtdome.InternalMotionState.STATIONARY.name]
                * mtdome.mock_llc.NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS

            await self.csc.statusLWSCS()
            lwscs_status = self.csc.lower_level_status[mtdome.LlcName.LWSCS.value]
            assert (
                lwscs_status["status"]["status"]
                == mtdome.InternalMotionState.STATIONARY.name
            )
            assert lwscs_status["positionActual"] == 0

            await self.csc.statusMonCS()
            moncs_status = self.csc.lower_level_status[mtdome.LlcName.MONCS.value]
            assert (
                moncs_status["status"]["status"]
                == mtdome.InternalMotionState.STATIONARY.name
            )
            assert moncs_status["data"] == [0.0] * mtdome.mock_llc.NUM_MON_SENSORS

            await self.csc.statusThCS()
            thcs_status = self.csc.lower_level_status[mtdome.LlcName.THCS.value]
            assert (
                thcs_status["status"]["status"]
                == mtdome.InternalMotionState.STATIONARY.name
            )
            assert (
                thcs_status["temperature"] == [0.0] * mtdome.mock_llc.NUM_THERMO_SENSORS
            )

    async def test_setZeroAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

            # Compensate for the dome azimuth offset.
            desired_position = utils.angle_wrap_nonnegative(
                2.0 - mtdome.DOME_AZIMUTH_OFFSET
            ).degree
            desired_velocity = 0.0
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
            await self.assert_command_replied(cmd=mtdome.CommandName.MOVE_AZ)
            data = await self.assert_next_sample(
                topic=self.remote.evt_azTarget, position=desired_position
            )
            assert desired_velocity == pytest.approx(data.velocity)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = (
                self.csc.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 0.1
            )

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.MOVING.name

            # Cannot set to zero while AMCS is MOVING
            with salobj.assertRaisesAckError():
                await self.remote.cmd_setZeroAz.set_start()
                await self.assert_command_replied(cmd="setZeroAz")

            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 2.0
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["positionActual"] == pytest.approx(math.radians(2.0))
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

            await self.remote.cmd_setZeroAz.set_start()
            await self.assert_command_replied(cmd="setZeroAz")

            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["positionActual"] == pytest.approx(0.0)
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

    async def test_homeShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            initial_position_actual = np.full(
                mtdome.mock_llc.NUM_SHUTTERS, 5.0, dtype=float
            )
            self.csc.mock_ctrl.apscs.position_actual = initial_position_actual

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()

            await self.csc.statusApSCS()
            status = self.csc.lower_level_status[mtdome.LlcName.APSCS.value]
            assert status["positionActual"] == initial_position_actual.tolist()

            sub_system_ids = SubSystemId.APSCS
            await self.remote.cmd_home.set_start(subSystemIds=sub_system_ids)
            await self.assert_command_replied(cmd="home")

            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1
            await self.csc.statusApSCS()
            status = self.csc.lower_level_status[mtdome.LlcName.APSCS.value]
            assert (
                status["positionActual"]
                == np.zeros(mtdome.mock_llc.NUM_SHUTTERS, dtype=float).tolist()
            )

    async def validate_operational_mode(
        self, operational_mode: OperationalMode, sub_system_ids: int
    ) -> None:
        await self.assert_command_replied(cmd="setOperationalMove")

        # Dictionary to look up which status telemetry function to call for
        # which sub_system.
        status_dict = {
            SubSystemId.AMCS: self.csc.statusAMCS,
            SubSystemId.APSCS: self.csc.statusApSCS,
            SubSystemId.CSCS: self.csc.statusCSCS,
            SubSystemId.LCS: self.csc.statusLCS,
            SubSystemId.LWSCS: self.csc.statusLWSCS,
            SubSystemId.MONCS: self.csc.statusMonCS,
            SubSystemId.RAD: self.csc.statusRAD,
            SubSystemId.THCS: self.csc.statusThCS,
        }
        events_to_check = []
        for sub_system_id in SubSystemId:
            if sub_system_id & sub_system_ids:
                func = status_dict[sub_system_id]
                name = mtdome.LlcNameDict[sub_system_id]
                await func()
                status = self.csc.lower_level_status[name]
                assert status["status"]["operationalMode"] == operational_mode.name
                events_to_check.append(sub_system_id.value)

        events_recevied = []
        for _ in range(len(events_to_check)):
            data = await self.assert_next_sample(
                topic=self.remote.evt_operationalMode,
                operationalMode=operational_mode,
                timeout=STD_TIMEOUT,
            )
            events_recevied.append(data.subSystemId)

        assert sorted(events_to_check) == sorted(events_recevied)

    async def test_do_setOperationalMode(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()

            # Test with one lower level component.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.AMCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set to NORMAL again.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set another lower level component to degraded.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.MONCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set the same, first, lower level component to degraded again.
            # This should not raise an exception.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.AMCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set two lower level components to normal.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS | SubSystemId.MONCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set two lower level components to normal again. This should not
            # raise an exception.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS | SubSystemId.MONCS
            await self.remote.cmd_setOperationalMode.set_start(
                operationalMode=operational_mode,
                subSystemIds=sub_system_ids,
            )
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

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
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

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
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

    async def test_slow_network(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.set_csc_to_enabled()
            self.csc.mock_ctrl.enable_slow_network = True

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
            assert desired_velocity == pytest.approx(data.velocity)

    @mock.patch.dict(
        "lsst.ts.mtdome.mtdome_csc.ALL_METHODS_AND_INTERVALS",
        {
            "statusAMCS": (0.2, True),
            "check_all_commands_have_replies": (600, True),
        },
    )
    async def test_network_interruption(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            await self.assert_next_summary_state(salobj.State.DISABLED)
            await self.set_csc_to_enabled()
            await self.assert_next_summary_state(salobj.State.ENABLED)
            self.csc.mock_ctrl.enable_network_interruption = True
            await self.assert_next_summary_state(salobj.State.FAULT)

    async def test_no_connection(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITHOUT_MOCK_CONTROLLER,
        ):
            await self.assert_next_summary_state(salobj.State.STANDBY)
            with pytest.raises(RuntimeError):
                await salobj.set_summary_state(
                    remote=self.remote, state=salobj.State.DISABLED
                )
            await self.assert_next_summary_state(salobj.State.FAULT)

    @mock.patch.dict(
        "lsst.ts.mtdome.mtdome_csc.ALL_METHODS_AND_INTERVALS",
        {
            "statusAMCS": (0.2, True),
            "check_all_commands_have_replies": (600, True),
        },
    )
    async def test_connection_lost(self) -> None:
        with open(CONFIG_DIR / "_init.yaml") as f:
            config = yaml.safe_load(f)

        async with self.create_mock_controller(
            port=config["port"]
        ) as mock_ctrl, self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITHOUT_MOCK_CONTROLLER,
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

    @mock.patch(
        "lsst.ts.mtdome.mtdome_csc._COMMANDS_REPLIED_PERIOD", COMMANDS_REPLIED_PERIOD
    )
    async def test_check_all_commands_have_replies(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=CONFIG_DIR,
            simulation_mode=mtdome.ValidSimulationMode.SIMULATION_WITH_MOCK_CONTROLLER,
        ):
            # Stop the background tasks to avoid interference with the test.
            await self.csc.cancel_periodic_tasks()
            self.csc.commands_without_reply.clear()

            # Mock a command that has not received a reply for a too long time.
            command_id = 1
            command = "cmd"
            tai = utils.current_tai() - 4.0 * COMMANDS_REPLIED_PERIOD
            assert command_id not in self.csc.commands_without_reply

            self.csc.commands_without_reply[command_id] = mtdome.CommandTime(
                command=command, tai=tai
            )
            assert command_id in self.csc.commands_without_reply

            await self.csc.check_all_commands_have_replies()
            assert command_id not in self.csc.commands_without_reply

    async def test_bin_script(self) -> None:
        await self.check_bin_script(name="MTDome", index=None, exe_name="run_mtdome")

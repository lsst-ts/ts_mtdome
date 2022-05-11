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

import logging
import math
import pathlib
import typing
import unittest

import numpy as np
import pytest

from lsst.ts import mtdome, salobj, utils
from lsst.ts.idl.enums.MTDome import (
    EnabledState,
    MotionState,
    OperationalMode,
    SubSystemId,
)

STD_TIMEOUT = 10  # standard command timeout (sec)
START_MOTORS_ADD_DURATION = 5.5

CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    def basic_make_csc(
        self,
        initial_state: salobj.State,
        config_dir: str,
        simulation_mode: int,
        **kwargs: typing.Any,
    ) -> None:
        return mtdome.MTDomeCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            mock_port=0,
        )

    async def test_standard_state_transitions(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.check_standard_state_transitions(
                enabled_commands=(
                    "moveAz",
                    "moveEl",
                    "stopAz",
                    "stopEl",
                    "stop",
                    "crawlAz",
                    "crawlEl",
                    "setLouvers",
                    "closeLouvers",
                    "stopLouvers",
                    "openShutter",
                    "closeShutter",
                    "stopShutter",
                    "park",
                    "goStationary",
                    "goStationaryAz",
                    "goStationaryEl",
                    "goStationaryLouvers",
                    "goStationaryShutter",
                    "setTemperature",
                    "exitFault",
                    "setOperationalMode",
                    "resetDrivesAz",
                    "setZeroAz",
                ),
            )

    async def test_version(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=mtdome.__version__,
                subsystemVersions="",
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
        await self.assert_next_sample(topic=self.remote.evt_brakesEngaged, brakes=0)
        await self.assert_next_sample(topic=self.remote.evt_interlocks, interlocks=0)
        await self.assert_next_sample(
            topic=self.remote.evt_lockingPinsEngaged, engaged=0
        )
        self.csc.mock_ctrl.determine_current_tai = self.determine_current_tai
        sub_system_ids = SubSystemId.AMCS
        await self.validate_operational_mode(
            operational_mode=OperationalMode.NORMAL, sub_system_ids=sub_system_ids
        )
        await self.assert_next_sample(topic=self.remote.evt_azConfigurationApplied)

    async def test_do_moveAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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

    @pytest.mark.skip(reason="Temporarily disabled because of the TMA pointing test.")
    async def test_do_moveEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
            simulation_mode=1,
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

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )

            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.AMCS
            )

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

    async def test_do_stopEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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

    async def test_do_stop(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
            )

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
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

    async def test_do_crawlAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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

    @pytest.mark.skip(reason="Temporarily disabled because of the TMA pointing test.")
    async def test_do_crawlEl(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
            simulation_mode=1,
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

    async def test_do_closeLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeLouvers.set_start()

    async def test_do_stopLouvers(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.LCS
            )

    async def test_do_openShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_openShutter.set_start()

    async def test_do_closeShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeShutter.set_start()

    async def test_do_stopShutter(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start(
                engageBrakes=False, subSystemIds=SubSystemId.APSCS
            )

    async def test_do_park(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
                topic=self.remote.evt_azTarget, position=0, velocity=0
            )

            # No new azMotion event gets emitted since the PARKED event already
            # was emitted and AMCS has not changed status since, so we're done.

    async def test_do_stop_and_brake(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert (
                amcs_status["status"]["status"] == mtdome.LlcMotionState.STATIONARY.name
            )

    async def test_do_setTemperature(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()
            desired_temperature = 10.0
            await self.remote.cmd_setTemperature.set_start(
                temperature=desired_temperature,
                timeout=STD_TIMEOUT,
            )

    async def test_config(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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

    async def test_fans(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.write_then_read_reply(
                command="fans", action=mtdome.OnOff.ON.value
            )

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["fans"] == mtdome.OnOff.ON.value

    async def test_inflate(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = utils.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.write_then_read_reply(
                command="inflate", action=mtdome.OnOff.ON.value
            )

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["status"]["inflate"] == mtdome.OnOff.ON.value

    async def test_status(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            # It should be possible to always execute the status command but
            # the connection with the lower level components only gets made in
            # DISABLED and ENABLED state  so that's why the state gets set to
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
            assert apscs_status["status"]["status"] == MotionState.CLOSED.name
            assert apscs_status["positionActual"] == [0.0, 0.0]

            await self.csc.statusLCS()
            lcs_status = self.csc.lower_level_status[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [MotionState.CLOSED.name] * mtdome.mock_llc.NUM_LOUVERS
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
            assert thcs_status["status"]["status"] == MotionState.CLOSED.name
            assert (
                thcs_status["temperature"]
                == [0.0] * mtdome.mock_llc.thcs.NUM_THERMO_SENSORS
            )

    async def test_status_error(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
            simulation_mode=1,
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

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
            )

            # Prepare the lower level components
            current_tai = self.csc.mock_ctrl.current_tai + 0.1
            drives_in_error = [1, 1, 0, 0, 0]
            await self.csc.mock_ctrl.amcs.set_fault(current_tai, drives_in_error)
            self.csc.mock_ctrl.apscs.status = MotionState.ERROR
            self.csc.mock_ctrl.lcs.status[:] = MotionState.ERROR.name
            self.csc.mock_ctrl.lwscs.status = MotionState.ERROR
            self.csc.mock_ctrl.moncs.status = MotionState.ERROR
            self.csc.mock_ctrl.thcs.status = MotionState.ERROR
            self.csc.mock_ctrl.amcs._commanded_motion_state = MotionState.ERROR
            self.csc.mock_ctrl.lwscs._commanded_motion_state = MotionState.ERROR

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == mtdome.LlcMotionState.ERROR.name

            # Cannot exit_fault with drives in error.
            with salobj.assertRaisesAckError():
                await self.remote.cmd_exitFault.set_start()

            reset = [1, 1, 0, 0, 0]
            await self.remote.cmd_resetDrivesAz.set_start(reset=reset)
            await self.remote.cmd_exitFault.set_start()

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert (
                amcs_status["status"]["status"] == mtdome.LlcMotionState.STATIONARY.name
            )

            await self.csc.statusApSCS()
            apscs_status = self.csc.lower_level_status[mtdome.LlcName.APSCS.value]
            assert (
                apscs_status["status"]["status"]
                == mtdome.LlcMotionState.STATIONARY.name
            )
            assert apscs_status["positionActual"] == [0.0, 0.0]

            await self.csc.statusLCS()
            lcs_status = self.csc.lower_level_status[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [mtdome.LlcMotionState.STATIONARY.name] * mtdome.mock_llc.NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS

            await self.csc.statusLWSCS()
            lwscs_status = self.csc.lower_level_status[mtdome.LlcName.LWSCS.value]
            assert (
                lwscs_status["status"]["status"]
                == mtdome.LlcMotionState.STATIONARY.name
            )
            assert lwscs_status["positionActual"] == 0

            await self.csc.statusMonCS()
            moncs_status = self.csc.lower_level_status[mtdome.LlcName.MONCS.value]
            assert (
                moncs_status["status"]["status"]
                == mtdome.LlcMotionState.STATIONARY.name
            )
            assert moncs_status["data"] == [0.0] * mtdome.mock_llc.NUM_MON_SENSORS

            await self.csc.statusThCS()
            thcs_status = self.csc.lower_level_status[mtdome.LlcName.THCS.value]
            assert (
                thcs_status["status"]["status"] == mtdome.LlcMotionState.STATIONARY.name
            )
            assert (
                thcs_status["temperature"] == [0.0] * mtdome.mock_llc.NUM_THERMO_SENSORS
            )

    async def test_setZeroAz(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
                2.0 + mtdome.DOME_AZIMUTH_OFFSET
            ).degree
            desired_velocity = 0.0
            await self.remote.cmd_moveAz.set_start(
                position=desired_position,
                velocity=desired_velocity,
                timeout=STD_TIMEOUT,
            )
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

            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 2.0
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["positionActual"] == pytest.approx(math.radians(2.0))
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

            await self.remote.cmd_setZeroAz.set_start()

            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[mtdome.LlcName.AMCS.value]
            assert amcs_status["positionActual"] == pytest.approx(0.0)
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name

    async def validate_operational_mode(
        self, operational_mode: OperationalMode, sub_system_ids: int
    ) -> None:
        # Dictionary to look up which status telemetry function to call for
        # which sub_system.
        status_dict = {
            SubSystemId.AMCS: self.csc.statusAMCS,
            SubSystemId.APSCS: self.csc.statusApSCS,
            SubSystemId.LCS: self.csc.statusLCS,
            SubSystemId.LWSCS: self.csc.statusLWSCS,
            SubSystemId.MONCS: self.csc.statusMonCS,
            SubSystemId.THCS: self.csc.statusThCS,
        }

        await self.remote.cmd_setOperationalMode.set_start(
            operationalMode=operational_mode,
            subSystemIds=sub_system_ids,
        )

        events_to_check = []
        for sub_system_id in SubSystemId:
            if sub_system_id & sub_system_ids:
                func = status_dict[sub_system_id]
                name = mtdome.LlcNameDict[sub_system_id]
                await func()
                status = self.csc.lower_level_status[name]
                assert status["status"]["operationalMode"] == operational_mode.name
                events_to_check.append(sub_system_id)

        events_recevied = []
        for i in range(len(events_to_check)):
            data = await self.assert_next_sample(
                topic=self.remote.evt_operationalMode,
                operationalMode=operational_mode,
                timeout=STD_TIMEOUT,
            )
            events_recevied.append(data.subSystemId)

        assert events_to_check == events_recevied

    async def test_do_setOperationalMode(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        ):
            await self.set_csc_to_enabled()

            # When the lower level components are enabled, events are sent to
            # indicate their OperationalMode.
            for i in range(len(list(SubSystemId))):
                await self.assert_next_sample(
                    topic=self.remote.evt_operationalMode,
                    operationalMode=OperationalMode.NORMAL,
                    timeout=STD_TIMEOUT,
                )

            # Test with one lower level component.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.AMCS
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set another lower level component to degraded.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.MONCS
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set the same, first, lower level component to degraded again.
            # This should not raise an exsception.
            operational_mode = OperationalMode.DEGRADED
            sub_system_ids = SubSystemId.AMCS
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set two lower level components to normal.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS | SubSystemId.MONCS
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

            # Set two lower level components to normal again. This should not
            # raise an exception.
            operational_mode = OperationalMode.NORMAL
            sub_system_ids = SubSystemId.AMCS | SubSystemId.MONCS
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
            await self.validate_operational_mode(
                operational_mode=operational_mode, sub_system_ids=sub_system_ids
            )

    async def test_slow_network(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.STANDBY,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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

    async def test_network_interruption(self) -> None:
        async with self.make_csc(
            initial_state=salobj.State.DISABLED,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
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
            simulation_mode=1,
        ):
            await self.assert_next_summary_state(salobj.State.STANDBY)
            self.csc.mock_ctrl_refuse_connections = True
            with pytest.raises(RuntimeError):
                await salobj.set_summary_state(
                    remote=self.remote, state=salobj.State.DISABLED
                )
            await self.assert_next_summary_state(salobj.State.FAULT)

    async def test_bin_script(self) -> None:
        await self.check_bin_script(name="MTDome", index=None, exe_name="run_mtdome.py")

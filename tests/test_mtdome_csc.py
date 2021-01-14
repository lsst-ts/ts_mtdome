# This file is part of ts_MTDome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the Vera Rubin Observatory
# Project (https://www.lsst.org).
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

import asynctest
import logging

import numpy as np

from lsst.ts import MTDome
from lsst.ts.MTDome.llc_name import LlcName
from lsst.ts.MTDome.mock_llc.lcs import NUM_LOUVERS
from lsst.ts.MTDome.mock_llc.moncs import NUM_MON_SENSORS
from lsst.ts.MTDome.mock_llc.thcs import NUM_THERMO_SENSORS
from lsst.ts import salobj
from lsst.ts.idl.enums.MTDome import EnabledState, MotionState

STD_TIMEOUT = 2  # standard command timeout (sec)

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)


class CscTestCase(salobj.BaseCscTestCase, asynctest.TestCase):
    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        return MTDome.MTDomeCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
            mock_port=0,
        )

    async def test_standard_state_transitions(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
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
                    "setTemperature",
                ),
            )

    async def set_csc_to_enabled(self):
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

    async def test_unsupported_command(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            try:
                # This command is not supported by the DomeCsc so an Error
                # should be returned by the controller leading to a KeyError in
                # MTDomeCsc.
                await self.csc.write_then_read_reply(
                    command="unsupported_command", parameters={}
                )
                self.fail("Expected a KeyError.")
            except KeyError:
                pass

    async def test_incorrect_parameter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            try:
                # This command is supported by the MTDomeCsc but it takes an
                # argument so an Error should be returned by the controller
                # leading to a ValueError in MTDomeCsc.
                await self.csc.write_then_read_reply(command="moveAz", parameters={})
                self.fail("Expected a ValueError.")
            except ValueError:
                pass

    async def test_do_moveAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
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
            self.assertAlmostEqual(desired_velocity, data.velocity)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(
                amcs_status["status"]["status"], MotionState.MOVING.name,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )

    async def test_do_moveEl(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
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
            amcs_status = self.csc.lower_level_status[LlcName.LWSCS.value]
            self.assertEqual(
                amcs_status["status"], MotionState.MOVING.name,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.MOVING,
                inPosition=False,
            )

    async def test_do_stopAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stopAz.set_start()

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

    async def test_do_stopEl(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stopEl.set_start()

            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

    async def test_do_stop(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stop.set_start()

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

    async def test_do_crawlAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            desired_velocity = 0.1
            await self.remote.cmd_crawlAz.set_start(
                velocity=desired_velocity, timeout=STD_TIMEOUT,
            )
            data = await self.assert_next_sample(topic=self.remote.evt_azTarget,)
            self.assertTrue(np.isnan(data.position))
            self.assertAlmostEqual(desired_velocity, data.velocity)

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(
                amcs_status["status"]["status"], MotionState.CRAWLING.name,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.CRAWLING,
                inPosition=True,
            )

    async def test_do_crawlEl(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
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
                velocity=desired_velocity, timeout=STD_TIMEOUT,
            )
            data = await self.assert_next_sample(topic=self.remote.evt_elTarget,)
            self.assertTrue(np.isnan(data.position))
            self.assertAlmostEqual(desired_velocity, data.velocity)

            # Now also check the elMotion event.
            await self.csc.statusLWSCS()
            amcs_status = self.csc.lower_level_status[LlcName.LWSCS.value]
            self.assertEqual(
                amcs_status["status"], MotionState.CRAWLING.name,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.CRAWLING,
                inPosition=True,
            )

    async def test_do_setLouvers(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            louver_id = 5
            target_position = 100
            desired_position = np.full(NUM_LOUVERS, -1.0, dtype=float)
            desired_position[louver_id] = target_position
            await self.remote.cmd_setLouvers.set_start(
                position=desired_position.tolist(), timeout=STD_TIMEOUT,
            )

    async def test_do_closeLouvers(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeLouvers.set_start()

    async def test_do_stopLouvers(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stopLouvers.set_start()

    async def test_do_openShutter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_openShutter.set_start()

    async def test_do_closeShutter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_closeShutter.set_start()

    async def test_do_stopShutter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            await self.remote.cmd_stopShutter.set_start()

    async def test_do_park(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            await self.remote.cmd_park.set_start()
            await self.assert_next_sample(
                topic=self.remote.evt_azTarget, position=0, velocity=0
            )

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            # Now also check the azMotion event.
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(
                amcs_status["status"]["status"], MotionState.PARKED.name,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.PARKED,
                inPosition=True,
            )

    async def test_do_setTemperature(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()
            desired_temperature = 10.0
            await self.remote.cmd_setTemperature.set_start(
                temperature=desired_temperature, timeout=STD_TIMEOUT,
            )

    async def test_config(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1,
        ):
            await self.set_csc_to_enabled()

            # All values are below the limits.
            system = LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
                {"target": "vmax", "setting": [1.0]},
            ]
            await self.csc.config_llcs(system, settings)

            # The value of AMCS amax is too high.
            system = LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [1.0]},
                {"target": "vmax", "setting": [1.0]},
            ]
            try:
                await self.csc.config_llcs(system, settings)
                self.fail("Expected a ValueError.")
            except ValueError:
                pass

            # The value of AMCS amax is too low.
            system = LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [-0.5]},
                {"target": "vmax", "setting": [1.0]},
            ]
            try:
                await self.csc.config_llcs(system, settings)
                self.fail("Expected a ValueError.")
            except ValueError:
                pass

            # The param AMCS smax doesn't exist.
            system = LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
                {"target": "vmax", "setting": [1.0]},
                {"target": "smax", "setting": [1.0]},
            ]
            try:
                await self.csc.config_llcs(system, settings)
                self.fail("Expected a KeyError.")
            except KeyError:
                pass

            # No parameter can be missing.
            system = LlcName.AMCS.value
            settings = [
                {"target": "jmax", "setting": [1.0]},
                {"target": "amax", "setting": [0.5]},
            ]
            try:
                await self.csc.config_llcs(system, settings)
                self.fail("Expected a KeyError.")
            except KeyError:
                pass

    async def test_fans(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.write_then_read_reply(
                command="fans", action=MTDome.OnOff.ON.value
            )

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(amcs_status["status"]["status"], MotionState.STOPPED.name)
            self.assertEqual(amcs_status["status"]["fans"], MTDome.OnOff.ON.value)

    async def test_inflate(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await self.set_csc_to_enabled()

            # Set the TAI time in the mock controller for easier control
            self.csc.mock_ctrl.current_tai = salobj.current_tai()
            # Set the mock device status TAI time to the mock controller time
            # for easier control
            self.csc.mock_ctrl.amcs.command_time_tai = self.csc.mock_ctrl.current_tai

            await self.csc.write_then_read_reply(
                command="inflate", action=MTDome.OnOff.ON.value
            )

            # Give some time to the mock device to move.
            self.csc.mock_ctrl.current_tai = self.csc.mock_ctrl.current_tai + 0.1

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(amcs_status["status"]["status"], MotionState.STOPPED.name)
            self.assertEqual(amcs_status["status"]["inflate"], MTDome.OnOff.ON.value)

    async def test_status(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1,
        ):
            # It should be possible to always execute the status command but
            # the connection with the lower level components only gets made in
            # DISABLED and ENABLED state  so that's why the state gets set to
            # ENABLED here.
            await self.set_csc_to_enabled()

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(
                amcs_status["status"]["status"], MotionState.STOPPED.name,
            )
            self.assertEqual(
                amcs_status["positionActual"], 0,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_azMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            await self.csc.statusApSCS()
            apscs_status = self.csc.lower_level_status[LlcName.APSCS.value]
            self.assertEqual(
                apscs_status["status"], MotionState.CLOSED.name,
            )
            self.assertEqual(
                apscs_status["positionActual"], 0,
            )

            await self.csc.statusLCS()
            lcs_status = self.csc.lower_level_status[LlcName.LCS.value]
            self.assertEqual(
                lcs_status["status"], [MotionState.CLOSED.name] * NUM_LOUVERS,
            )
            self.assertEqual(
                lcs_status["positionActual"], [0.0] * NUM_LOUVERS,
            )

            await self.csc.statusLWSCS()
            lwscs_status = self.csc.lower_level_status[LlcName.LWSCS.value]
            self.assertEqual(
                lwscs_status["status"], MotionState.STOPPED.name,
            )
            self.assertEqual(
                lwscs_status["positionActual"], 0,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_elMotion,
                state=MotionState.STOPPED,
                inPosition=True,
            )

            await self.csc.statusMonCS()
            moncs_status = self.csc.lower_level_status[LlcName.MONCS.value]
            self.assertEqual(
                moncs_status["status"], MotionState.CLOSED.name,
            )
            self.assertEqual(
                moncs_status["data"], [0.0] * NUM_MON_SENSORS,
            )

            await self.csc.statusThCS()
            thcs_status = self.csc.lower_level_status[LlcName.THCS.value]
            self.assertEqual(
                thcs_status["status"], MotionState.CLOSED.name,
            )
            self.assertEqual(
                thcs_status["temperature"], [0.0] * NUM_THERMO_SENSORS,
            )

    async def test_status_error(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1,
        ):
            await self.set_csc_to_enabled()

            # Introduce an error. This will be improved once error codes have
            # been specified in a future Dome Software meeting.
            expected_error = [
                "Drive 1 temperature too high",
                "Drive 2 temperature too high",
            ]
            expected_fault_code = ", ".join(expected_error)
            self.csc.mock_ctrl.amcs.error = expected_error
            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(
                amcs_status["status"]["status"], MotionState.STOPPED.name,
            )
            self.assertEqual(
                amcs_status["status"]["error"], expected_error,
            )
            self.assertEqual(
                amcs_status["positionActual"], 0,
            )
            await self.assert_next_sample(
                topic=self.remote.evt_azEnabled,
                state=EnabledState.FAULT,
                faultCode=expected_fault_code,
            )

    async def test_bin_script(self):
        await self.check_bin_script(name="MTDome", index=None, exe_name="run_mtdome.py")

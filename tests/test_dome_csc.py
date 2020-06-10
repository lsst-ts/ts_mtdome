import asynctest
import logging

from lsst.ts import salobj
from lsst.ts import Dome
from lsst.ts.Dome.llc_name import LlcName

STD_TIMEOUT = 2  # standard command timeout (sec)
NUM_LOUVERS = 34
NUM_MON_SENSORS = 16
NUM_THERMO_SENSORS = 16

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)


class CscTestCase(salobj.BaseCscTestCase, asynctest.TestCase):
    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        return Dome.DomeCsc(
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
                    "setLouver",
                    "closeLouvers",
                    "stopLouvers",
                    "openShutter",
                    "closeShutter",
                    "stopShutter",
                    "park",
                    "setTemperature",
                ),
            )

    async def test_unsupported_command(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            try:
                # This command is not supported by the DomeCsc so an Error should be returned by the
                # controller leading to a KeyError in DomeCsc
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
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            try:
                # This command is supported by the DomeCsc but it takes an argument so an Error should be
                # returned by the controller leading to a ValueError in DomeCsc
                await self.csc.write_then_read_reply(command="moveAz", parameters={})
                self.fail("Expected a ValueError.")
            except ValueError:
                pass

    async def test_do_moveAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_azimuth = 40
            desired_velocity = 0.1
            await self.remote.cmd_moveAz.set_start(
                azimuth=desired_azimuth, azRate=desired_velocity, timeout=STD_TIMEOUT
            )

    async def test_do_moveEl(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_elevation = 40
            await self.remote.cmd_moveEl.set_start(
                elevation=desired_elevation, timeout=STD_TIMEOUT
            )

    async def test_do_stopAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_stopAz.set_start()

    async def test_do_stopEl(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_stopEl.set_start()

    async def test_do_stop(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_stop.set_start()

    async def test_do_crawlAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_velocity = 0.1
            await self.remote.cmd_crawlAz.set_start(
                azRate=desired_velocity, timeout=STD_TIMEOUT,
            )

    async def test_do_crawlEl(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_velocity = 0.1
            await self.remote.cmd_crawlEl.set_start(
                elRate=desired_velocity, timeout=STD_TIMEOUT,
            )

    async def test_do_setLouver(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_id = 5
            desired_position = 60
            await self.remote.cmd_setLouver.set_start(
                id=desired_id, position=desired_position, timeout=STD_TIMEOUT,
            )

    async def test_do_closeLouvers(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_closeLouvers.set_start()

    async def test_do_stopLouvers(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_stopLouvers.set_start()

    async def test_do_openShutter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_openShutter.set_start()

    async def test_do_closeShutter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_closeShutter.set_start()

    async def test_do_stopShutter(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_stopShutter.set_start()

    async def test_do_park(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.remote.cmd_park.set_start()

    async def test_do_setTemperature(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_temperature = 10.0
            await self.remote.cmd_setTemperature.set_start(
                temperature=desired_temperature, timeout=STD_TIMEOUT,
            )

    async def test_config(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1,
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )

            # All values are below the limits.
            config = {
                LlcName.AMCS.value: {"jmax": 1.0, "amax": 0.5, "vmax": 1.0},
                LlcName.LWSCS.value: {"jmax": 1.0, "amax": 0.5, "vmax": 1.0},
            }
            await self.csc.config_llcs(config)

            # The value of AMCS amax is too high.
            config = {
                LlcName.AMCS.value: {"jmax": 1.0, "amax": 1.0, "vmax": 1.0},
                LlcName.LWSCS.value: {"jmax": 1.0, "amax": 0.5, "vmax": 1.0},
            }
            try:
                await self.csc.config_llcs(config)
                self.fail("Expected a ValueError.")
            except ValueError:
                pass

            # The param AMCS smax doesn't exist.
            config = {
                LlcName.AMCS.value: {
                    "jmax": 1.0,
                    "amax": 0.5,
                    "vmax": 1.0,
                    "smax": 1.0,
                },
                LlcName.LWSCS.value: {"jmax": 1.0, "amax": 0.5, "vmax": 1.0},
            }
            try:
                await self.csc.config_llcs(config)
                self.fail("Expected a KeyError.")
            except KeyError:
                pass

            # No parameter can be missing.
            config = {
                LlcName.AMCS.value: {"jmax": 1.0, "amax": 0.5},
                LlcName.LWSCS.value: {"jmax": 1.0, "amax": 0.5, "vmax": 1.0},
            }
            try:
                await self.csc.config_llcs(config)
                self.fail("Expected a KeyError.")
            except KeyError:
                pass

    async def test_fans(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.csc.write_then_read_reply(
                command="fans", parameters={"action": Dome.OnOff.ON.name}
            )

    async def test_inflate(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.csc.write_then_read_reply(
                command="inflate", parameters={"action": Dome.OnOff.ON.name}
            )

    async def test_status(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1,
        ):
            # It should be possible to always execute the status command but the connection with the lower
            # level components only gets made in DISABLED and ENABLED state so that's why the state gets
            # set to ENABLED here.
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )

            await self.csc.statusAMCS()
            amcs_status = self.csc.lower_level_status[LlcName.AMCS.value]
            self.assertEqual(
                amcs_status["status"], Dome.LlcStatus.STOPPED.value,
            )
            self.assertEqual(
                amcs_status["positionActual"], 0,
            )

            await self.csc.statusApSCS()
            apscs_status = self.csc.lower_level_status[LlcName.APSCS.value]
            self.assertEqual(
                apscs_status["status"], Dome.LlcStatus.CLOSED.value,
            )
            self.assertEqual(
                apscs_status["positionActual"], 0,
            )

            await self.csc.statusLCS()
            lcs_status = self.csc.lower_level_status[LlcName.LCS.value]
            self.assertEqual(
                lcs_status["status"], [Dome.LlcStatus.CLOSED.value] * NUM_LOUVERS,
            )
            self.assertEqual(
                lcs_status["positionActual"], [0.0] * NUM_LOUVERS,
            )

            await self.csc.statusLWSCS()
            lwscs_status = self.csc.lower_level_status[LlcName.LWSCS.value]
            self.assertEqual(
                lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
            )
            self.assertEqual(
                lwscs_status["positionActual"], 0,
            )

            await self.csc.statusMonCS()
            moncs_status = self.csc.lower_level_status[LlcName.MONCS.value]
            self.assertEqual(
                moncs_status["status"], Dome.LlcStatus.DISABLED.value,
            )
            self.assertEqual(
                moncs_status["data"], [0.0] * NUM_MON_SENSORS,
            )

            await self.csc.statusThCS()
            thcs_status = self.csc.lower_level_status[LlcName.THCS.value]
            self.assertEqual(
                thcs_status["status"], Dome.LlcStatus.DISABLED.value,
            )
            self.assertEqual(
                thcs_status["data"], [0.0] * NUM_THERMO_SENSORS,
            )

    # TODO uncomment once it is clear why this test case suddenly is failing.
    async def test_bin_script(self):
        await self.check_bin_script(name="Dome", index=None, exe_name="run_dome.py")

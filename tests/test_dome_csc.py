import asynctest
import status_assert_util as sau
import unittest

from lsst.ts import salobj
from lsst.ts import Dome
from lsst.ts.Dome import task_scheduler

STD_TIMEOUT = 2  # standard command timeout (sec)


class CscTestCase(salobj.BaseCscTestCase, asynctest.TestCase):
    def basic_make_csc(self, initial_state, config_dir, simulation_mode):
        return Dome.DomeCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=simulation_mode,
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
                    "config",
                    "fans",
                    "inflate",
                    "status",
                )
            )

    async def test_do_moveAz(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1
        ):
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            desired_azimuth = 40
            await self.remote.cmd_moveAz.set_start(
                azimuth=desired_azimuth, timeout=STD_TIMEOUT
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
        raise unittest.SkipTest("Not implemented")

    async def test_do_crawlAz(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_crawlEl(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_setLouver(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_closeLouvers(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_stopLouvers(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_openShutter(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_closeShutter(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_stopShutter(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_park(self):
        raise unittest.SkipTest("Not implemented")

    async def test_do_setTemperature(self):
        raise unittest.SkipTest("Not implemented")

    async def test_config(self):
        raise unittest.SkipTest("Not implemented")

    async def test_fans(self):
        raise unittest.SkipTest("Not implemented")

    async def test_inflate(self):
        raise unittest.SkipTest("Not implemented")

    async def test_status(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=None, simulation_mode=1,
        ):
            task_scheduler.run_status_loop = True
            # It should be possible to always execute the status command but the connection with the lower
            # level components only gets made in DISABLED and ENABLED state so that's why the state gets
            # set to ENABLED here.
            await salobj.set_summary_state(
                remote=self.remote, state=salobj.State.ENABLED
            )
            await self.csc.status()
            sau.assertReply(
                "AMCS", self.csc.lower_level_status, status="Stopped", positionActual=0
            )
            sau.assertReply(
                "ApCS", self.csc.lower_level_status, status="Stopped", positionActual=0
            )
            sau.assertTBD("LCS", self.csc.lower_level_status)
            sau.assertTBD("LWCS", self.csc.lower_level_status)
            sau.assertTBD("ThCS", self.csc.lower_level_status)
            sau.assertTBD("MonCS", self.csc.lower_level_status)

    async def test_bin_script(self):
        await self.check_bin_script(name="Dome", index=None, exe_name="run_dome.py")

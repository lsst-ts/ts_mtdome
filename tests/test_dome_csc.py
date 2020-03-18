import asynctest

# import unittest
from lsst.ts import salobj
from lsst.ts import Dome


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
        pass

    async def test_do_moveEl(self):
        pass

    async def test_do_stopAz(self):
        pass

    async def test_do_stopEl(self):
        pass

    async def test_do_stop(self):
        pass

    async def test_do_crawlAz(self):
        pass

    async def test_do_crawlEl(self):
        pass

    async def test_do_setLouver(self):
        pass

    async def test_do_closeLouvers(self):
        pass

    async def test_do_stopLouvers(self):
        pass

    async def test_do_openShutter(self):
        pass

    async def test_do_closeShutter(self):
        pass

    async def test_do_stopShutter(self):
        pass

    async def test_do_park(self):
        pass

    async def test_do_setTemperature(self):
        pass

    async def test_config(self):
        pass

    async def test_fans(self):
        pass

    async def test_inflate(self):
        pass

    async def test_status(self):
        pass

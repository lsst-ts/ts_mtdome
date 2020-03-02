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

    async def test_do_Dome_command_crawlAz(self, id_data):
        pass

    async def test_do_Dome_command_crawlEl(self, id_data):
        pass

    async def test_do_Dome_command_moveAz(self, id_data):
        pass

    async def test_do_Dome_command_moveEl(self, id_data):
        pass

    async def test_do_Dome_command_park(self, id_data):
        pass

    async def test_do_Dome_command_setLouver(self, id_data):
        pass

    async def test_do_Dome_command_closeLouvers(self, id_data):
        pass

    async def test_do_Dome_command_stopLouvers(self, id_data):
        pass

    async def test_do_Dome_command_closeShutter(self, id_data):
        pass

    async def test_do_Dome_command_openShutter(self, id_data):
        pass

    async def test_do_Dome_command_stopShutter(self, id_data):
        pass

    async def test_do_Dome_command_stopAz(self, id_data):
        pass

    async def test_do_Dome_command_stopEl(self, id_data):
        pass

    async def test_do_Dome_command_stop(self, id_data):
        pass

    async def test_do_Dome_command_setTemperature(self, id_data):
        pass

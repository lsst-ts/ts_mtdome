import asyncio
import asynctest
import logging
import math
import yaml

from lsst.ts import Dome

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.INFO
)

_DEGREES_TO_RADIANS = math.pi / 180.0
_NUM_LOUVERS = 34
_NUM_MON_SENSORS = 16
_NUM_THERMO_SENSORS = 16


class MockTestCase(asynctest.TestCase):
    async def setUp(self):
        self.ctrl = None
        self.writer = None
        port = 0
        self.mock_ctrl = None
        self.data = None
        self.log = logging.getLogger("MockTestCase")

        self.mock_ctrl = Dome.MockDomeController(port=port)
        asyncio.create_task(self.mock_ctrl.start())
        await asyncio.sleep(1)
        # Request the assigned port from the mock controller.
        port = self.mock_ctrl.port

        rw_coro = asyncio.open_connection(host="127.0.0.1", port=port)
        self.reader, self.writer = await asyncio.wait_for(rw_coro, timeout=1)

    async def read(self):
        """Utility function to read a string from the reader and unmarshal it

        Returns
        -------
        configuration_parameters : `dict`
            A dictionary with objects representing the string read.
        """
        read_bytes = await asyncio.wait_for(self.reader.readuntil(b"\r\n"), timeout=1)
        data = yaml.safe_load(read_bytes.decode())
        return data

    async def write(self, st):
        """Utility function to write a string to the writer.

        Parameters
        ----------
        st : `str`
            The string to write.
        """
        self.writer.write(st.encode() + b"\r\n")
        await self.writer.drain()

    async def tearDown(self):
        if self.mock_ctrl:
            await asyncio.wait_for(self.mock_ctrl.stop(), 5)
        if self.writer:
            self.writer.close()

    async def test_command_does_not_exist(self):
        await self.write("non-existent_command:\n")
        self.data = await self.read()
        self.assertEqual(self.data["ERROR"]["CODE"], 2)

    async def test_missing_command_parameter(self):
        await self.write("moveAz:\n")
        self.data = await self.read()
        self.assertEqual(self.data["ERROR"]["CODE"], 3)

    async def test_moveAz(self):
        target_azimuth = 10 * _DEGREES_TO_RADIANS
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], 0.5 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            amcs_status["positionActual"], 1.5 * _DEGREES_TO_RADIANS,
        )

        # Give some time to the mock device to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], 2.5 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            amcs_status["positionActual"], 3.5 * _DEGREES_TO_RADIANS,
        )

        # Give some time to the mock device to reach the commanded position.
        await asyncio.sleep(5)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            amcs_status["positionActual"], 10.0 * _DEGREES_TO_RADIANS,
        )

    async def test_crawlAz(self):
        target_rate = 0.1 * _DEGREES_TO_RADIANS
        await self.write(f"crawlAz:\n dirMotion: CW\n azRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to move
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.CRAWLING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], 0.05 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            amcs_status["positionActual"], 0.15 * _DEGREES_TO_RADIANS,
        )

    async def test_stopAz(self):
        target_azimuth = 10 * _DEGREES_TO_RADIANS
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to move
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], 0.5 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            amcs_status["positionActual"], 1.5 * _DEGREES_TO_RADIANS,
        )

        await self.write("stopAz:\n")
        # Give some time to the mock device to stop moving.
        await asyncio.sleep(0.2)
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.short_timeout)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], 1.0 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            amcs_status["positionActual"], 1.7 * _DEGREES_TO_RADIANS,
        )

    async def test_moveEl(self):
        target_elevation = 5 * _DEGREES_TO_RADIANS
        await self.write(f"moveEl:\n elevation: {target_elevation}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], 1.5 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], 2.0 * _DEGREES_TO_RADIANS,
        )

        # Give some time to the mock device to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], 3.0 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], 4.0 * _DEGREES_TO_RADIANS,
        )

        # Give some time to the mock device to reach the commanded position.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            lwscs_status["positionActual"], 5.0 * _DEGREES_TO_RADIANS,
        )

    async def test_stopEl(self):
        target_elevation = 5 * _DEGREES_TO_RADIANS
        await self.write(f"moveEl:\n elevation: {target_elevation}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], 1.5 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], 2.0 * _DEGREES_TO_RADIANS,
        )

        await self.write("stopEl:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.short_timeout)

        # Give some time to the mock device to stop moving.
        await asyncio.sleep(0.1)
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], 1.5 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], 2.0 * _DEGREES_TO_RADIANS,
        )

    async def test_stop(self):
        target_azimuth = 10 * _DEGREES_TO_RADIANS
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        target_elevation = 5 * _DEGREES_TO_RADIANS
        await self.write(f"moveEl:\n elevation: {target_elevation}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        await self.write("setLouver:\n id: 5\n position: 90.0\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        await self.write("openShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        await self.write("stop:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock devices to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            status["status"], Dome.LlcStatus.STOPPED.value,
        )
        status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            status["status"], Dome.LlcStatus.STOPPED.value,
        )
        status = self.data[Dome.LlcName.LCS.value]
        self.assertEqual(
            status["status"], [Dome.LlcStatus.STOPPED.value] * _NUM_LOUVERS,
        )
        status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            status["status"], Dome.LlcStatus.STOPPED.value,
        )

    async def test_crawlEl(self):
        target_rate = 0.1 * _DEGREES_TO_RADIANS
        await self.write(f"crawlEl:\n dirMotion: UP\n elRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to move.
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.CRAWLING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], 0.05 * _DEGREES_TO_RADIANS,
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], 0.15 * _DEGREES_TO_RADIANS,
        )

    async def test_setLouver(self):
        louver_id = 5
        target_position = 90 * _DEGREES_TO_RADIANS
        await self.write(
            f"setLouver:\n id: {louver_id}\n position: {target_position}\n"
        )
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to open.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        lcs_status = self.data[Dome.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"],
            [Dome.LlcStatus.CLOSED.value] * louver_id
            + [Dome.LlcStatus.OPEN.value]
            + [Dome.LlcStatus.CLOSED.value] * (_NUM_LOUVERS - louver_id - 1),
        )
        self.assertEqual(
            lcs_status["positionActual"],
            [0.0] * louver_id
            + [target_position]
            + [0.0] * (_NUM_LOUVERS - louver_id - 1),
        )
        self.assertEqual(
            lcs_status["positionCmd"],
            [0.0] * louver_id
            + [target_position]
            + [0.0] * (_NUM_LOUVERS - louver_id - 1),
        )

    async def test_closeLouvers(self):
        await self.write("closeLouvers:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to close.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        lcs_status = self.data[Dome.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"], [Dome.LlcStatus.CLOSED.value] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"], [0.0] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionCmd"], [0.0] * _NUM_LOUVERS,
        )

    async def test_stopLouvers(self):
        louver_id = 5
        target_position = 90 * _DEGREES_TO_RADIANS
        await self.write(
            f"setLouver:\n id: {louver_id}\n position: {target_position}\n"
        )
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to open.
        await asyncio.sleep(0.2)
        await self.write("stopLouvers:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to stop.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        lcs_status = self.data[Dome.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"], [Dome.LlcStatus.STOPPED.value] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"],
            [0.0] * louver_id
            + [target_position]
            + [0.0] * (_NUM_LOUVERS - louver_id - 1),
        )
        self.assertEqual(
            lcs_status["positionCmd"],
            [0.0] * louver_id
            + [target_position]
            + [0.0] * (_NUM_LOUVERS - louver_id - 1),
        )

    async def test_openShutter(self):
        await self.write("openShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to open.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        apscs_status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.OPEN.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 90.0 * _DEGREES_TO_RADIANS,
        )
        self.assertEqual(
            apscs_status["positionCmd"], 90.0 * _DEGREES_TO_RADIANS,
        )

    async def test_closeShutter(self):
        await self.write("closeShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to close.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        apscs_status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.CLOSED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 0.0,
        )
        self.assertEqual(
            apscs_status["positionCmd"], 0.0,
        )

    async def test_stopShutter(self):
        await self.write("openShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to open.
        await asyncio.sleep(0.2)
        await self.write("stopShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to stop.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        apscs_status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 90.0 * _DEGREES_TO_RADIANS,
        )
        self.assertEqual(
            apscs_status["positionCmd"], 90.0 * _DEGREES_TO_RADIANS,
        )

    async def test_config(self):
        config = {
            Dome.LlcName.AMCS.value: {
                "jmax": 3.0 * _DEGREES_TO_RADIANS,
                "amax": 0.75 * _DEGREES_TO_RADIANS,
                "vmax": 1.5 * _DEGREES_TO_RADIANS,
            },
            Dome.LlcName.LWSCS.value: {
                "jmax": 3.5 * _DEGREES_TO_RADIANS,
                "amax": 0.875 * _DEGREES_TO_RADIANS,
                "vmax": 1.75 * _DEGREES_TO_RADIANS,
            },
        }
        await self.write(f"config:\n {config}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

    async def test_park(self):
        target_azimuth = 1 * _DEGREES_TO_RADIANS
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to move.
        await asyncio.sleep(0.2)
        await self.write("park:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to park.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.PARKED.value,
        )
        self.assertEqual(
            amcs_status["positionActual"], 0,
        )
        self.assertEqual(
            amcs_status["positionCmd"], 0,
        )

    async def test_setTemperature(self):
        temperature = 10.0
        await self.write(f"setTemperature:\n temperature: {temperature}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # Give some time to the mock device to set the temperature.
        await asyncio.sleep(0.2)
        await self.write("status:\n")
        self.data = await self.read()
        self.log.info(f"data = {self.data}")
        thcs_status = self.data[Dome.LlcName.THCS.value]
        self.assertEqual(
            thcs_status["status"], Dome.LlcStatus.ENABLED.value,
        )
        self.assertEqual(
            thcs_status["data"], [temperature] * _NUM_THERMO_SENSORS,
        )

    async def test_inflate(self):
        await self.write("inflate:\n action: True\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # The status of the inflatable seal is not part of the output of amcs status so this is the only
        # way to check the result of executing the inflate command
        self.assertTrue(self.mock_ctrl.amcs.seal_inflated)

    async def test_fans(self):
        await self.write("fans:\n action: True\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)
        # The status of the fans is not part of the output of amcs status so this is the only way to check
        # the result of executing the fans command
        self.assertTrue(self.mock_ctrl.amcs.fans_enabled)

    async def test_status(self):
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            amcs_status["positionActual"], 0,
        )

        apscs_status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.CLOSED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 0,
        )

        lcs_status = self.data[Dome.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"], [Dome.LlcStatus.CLOSED.value] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"], [0.0] * _NUM_LOUVERS,
        )

        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            lwscs_status["positionActual"], 0,
        )

        moncs_status = self.data[Dome.LlcName.MONCS.value]
        self.assertEqual(
            moncs_status["status"], Dome.LlcStatus.DISABLED.value,
        )
        self.assertEqual(
            moncs_status["data"], [0.0] * _NUM_MON_SENSORS,
        )

        thcs_status = self.data[Dome.LlcName.THCS.value]
        self.assertEqual(
            thcs_status["status"], Dome.LlcStatus.DISABLED.value,
        )
        self.assertEqual(
            thcs_status["data"], [0.0] * _NUM_THERMO_SENSORS,
        )


if __name__ == "__main__":
    asynctest.main()

import asyncio
import asynctest
import yaml

from lsst.ts import Dome


class MockTestCase(asynctest.TestCase):
    async def setUp(self):
        self.ctrl = None
        self.writer = None
        self.port = 5000
        self.mock_ctrl = None
        self.data = None

        self.mock_ctrl = Dome.MockDomeController(port=self.port)
        asyncio.create_task(self.mock_ctrl.start())
        await asyncio.sleep(1)

        rw_coro = asyncio.open_connection(host="127.0.0.1", port=self.port)
        self.reader, self.writer = await asyncio.wait_for(rw_coro, timeout=1)
        self.data = await self.read()
        self.assertComponent("AMCS", {"status": "Stopped", "positionActual": 0})
        self.assertTBD("ApCS")
        self.assertTBD("LCS")
        self.assertTBD("LWCS")
        self.assertTBD("ThCS")
        self.assertTBD("MonCS")

    async def read(self):
        """ Utility function to read a string from the reader and unmarshal it
        """
        read_bytes = await asyncio.wait_for(
            self.reader.readuntil("\r\n".encode()), timeout=1
        )
        data = yaml.safe_load(read_bytes.decode())
        return data

    async def write(self, st):
        """ Utility function to write a string to the writer
        """
        self.writer.write(f"{st}\r\n".encode())
        await self.writer.drain()

    def assertComponent(self, component, expected):
        """ Asserts that the values of the AMCS parameter data are as expected
        """
        self.assertIn(component, self.data)
        for key in expected.keys():
            self.assertEqual(self.data[component][key], expected[key])

    def assertTBD(self, component):
        """ Asserts that the values of the component parameter data are as expected
        """
        self.assertIn(component, self.data)
        self.assertEqual(self.data[component], "TBD")

    async def tearDown(self):
        if self.mock_ctrl:
            await asyncio.wait_for(self.mock_ctrl.quit(), 5)
        if self.writer:
            self.writer.close()

    async def test_status(self):
        await self.write("status:\n")
        self.data = await self.read()
        self.assertComponent("AMCS", {"status": "Stopped", "positionActual": 0})
        self.assertTBD("ApCS")
        self.assertTBD("LCS")
        self.assertTBD("LWCS")
        self.assertTBD("ThCS")
        self.assertTBD("MonCS")

    async def test_moveAz(self):
        await self.write("moveAz:\n position: 10\n")
        self.data = await self.read()
        self.assertIn("OK", self.data)
        self.assertEqual(self.data["OK"], None)
        self.assertIn("Timeout", self.data)
        self.assertEqual(self.data["Timeout"], 20)
        await self.write("status:\n")
        self.data = await self.read()
        self.assertComponent(
            "AMCS", {"status": "Moving to position 10.0", "positionActual": 5}
        )
        await self.write("status:\n")
        self.data = await self.read()
        self.assertComponent(
            "AMCS", {"status": "Moving to position 10.0", "positionActual": 10}
        )
        await self.write("status:\n")
        self.data = await self.read()
        self.assertComponent("AMCS", {"status": "Stopped", "positionActual": 10})

    async def test_stopAz(self):
        await self.write("moveAz:\n position: 10\n")
        self.data = await self.read()
        self.assertIn("OK", self.data)
        self.assertEqual(self.data["OK"], None)
        self.assertIn("Timeout", self.data)
        self.assertEqual(self.data["Timeout"], 20)
        await self.write("status:\n")
        self.data = await self.read()
        self.assertComponent(
            "AMCS", {"status": "Moving to position 10.0", "positionActual": 5}
        )

        await self.write("stopAz:\n")
        self.data = await self.read()
        self.assertIn("OK", self.data)
        self.assertEqual(self.data["OK"], None)
        self.assertIn("Timeout", self.data)
        self.assertEqual(self.data["Timeout"], 2)

        await self.write("status:\n")
        self.data = await self.read()
        self.assertComponent("AMCS", {"status": "Stopped", "positionActual": 5})


if __name__ == "__main__":
    asynctest.main()

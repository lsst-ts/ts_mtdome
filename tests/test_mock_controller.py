import asyncio
import asynctest
import logging
import status_assert_util as sau
import yaml

from lsst.ts import Dome

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.INFO
)


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
            await asyncio.wait_for(self.mock_ctrl.quit(), 5)
        if self.writer:
            self.writer.close()

    async def test_command_does_not_exist(self):
        await self.write("non-existent_command:\n")
        self.data = await self.read()
        sau.assertReply("ERROR", self.data, CODE=2)

    async def test_missing_command_parameter(self):
        await self.write("moveAz:\n")
        self.data = await self.read()
        sau.assertReply("ERROR", self.data, CODE=3)

    async def test_status(self):
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("AMCS", self.data, status="Stopped", positionActual=0)
        sau.assertReply("LWSCS", self.data, status="Stopped", positionActual=0)
        sau.assertTBD("LCS", self.data)
        sau.assertTBD("ApCS", self.data)
        sau.assertTBD("ThCS", self.data)
        sau.assertTBD("MonCS", self.data)

    async def test_moveAz(self):
        await self.write("moveAz:\n azimuth: 10\n")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=20)
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("AMCS", self.data, status="Moving", positionActual=[0.5, 1.5])
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("AMCS", self.data, status="Moving", positionActual=[1.0, 2.0])
        await asyncio.sleep(5)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("AMCS", self.data, status="Stopped", positionActual=10)

    async def test_crawlAz(self):
        await self.write("crawlAz:\n dirMotion: CW\n azRate: 0.1")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=20)
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply(
            "AMCS", self.data, status="Crawling", positionActual=[0.05, 0.15]
        )

    async def test_stopAz(self):
        await self.write("moveAz:\n azimuth: 10\n")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=20)
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("AMCS", self.data, status="Moving", positionActual=[0.5, 1.5])
        await self.write("stopAz:\n")
        await asyncio.sleep(0.2)
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=2)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("AMCS", self.data, status="Stopped", positionActual=[1.0, 1.7])

    async def test_moveEl(self):
        await self.write("moveEl:\n elevation: 5\n")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=20)
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply(
            "LWSCS", self.data, status="Moving", positionActual=[1.5, 2.0],
        )
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        print(f"WOUTERRRRR {self.data}")
        sau.assertReply("LWSCS", self.data, status="Moving", positionActual=[3.0, 4.0])
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("LWSCS", self.data, status="Stopped", positionActual=5)

    async def test_stopEl(self):
        await self.write("moveEl:\n elevation: 5\n")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=20)
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply(
            "LWSCS", self.data, status="Moving", positionActual=[1.5, 2.0],
        )
        await self.write("stopEl:\n")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=2)
        await asyncio.sleep(1)
        await self.write("status:\n")
        self.data = await self.read()
        sau.assertReply("LWSCS", self.data, status="Stopped", positionActual=[1.5, 2.0])

    async def test_config(self):
        config = {
            "AMCS": {"jmax": 3.0, "amax": 0.75, "vmax": 1.5},
            "LWSCS": {"jmax": 3.5, "amax": 0.875, "vmax": 1.75},
        }
        await self.write(f"config:\n {config}\n")
        self.data = await self.read()
        sau.assertReply("OK", self.data, Timeout=20)


if __name__ == "__main__":
    asynctest.main()

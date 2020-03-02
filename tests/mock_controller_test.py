import asyncio
import unittest
import asynctest
from lsst.ts import Dome


class MockTestCase(asynctest.TestCase):
    async def setUp(self):
        self.ctrl = None
        self.writer = None
        self.port = 5000
        self.mock_ctrl = None

        self.mock_ctrl = Dome.MockDomeController(port=self.port)
        asyncio.create_task(self.mock_ctrl.start())
        await asyncio.sleep(1)

        rw_coro = asyncio.open_connection(host="127.0.0.1", port=self.port)
        self.reader, self.writer = await asyncio.wait_for(rw_coro, timeout=5)
        read_bytes = await asyncio.wait_for(
            self.reader.read(n=100), timeout=5
        )
        read_str = read_bytes.decode()
        self.assertEqual(read_str, "Enter Command > ")

    async def tearDown(self):
        if self.mock_ctrl:
            await asyncio.wait_for(self.mock_ctrl.quit(self.writer), 5)
        if self.writer:
            self.writer.close()

    async def test_mock_controller(self):
        self.writer.write("status\n".encode())
        await self.writer.drain()
        read_bytes = await asyncio.wait_for(
            self.reader.read(n=10000), timeout=5
        )
        read_str = read_bytes.decode()
        self.assertTrue('AMCS: ' in read_str)
        self.assertTrue('ApSCS: ' in read_str)
        self.assertTrue('LCS: ' in read_str)
        self.assertTrue('LWCS: ' in read_str)
        self.assertTrue('ThCS: ' in read_str)
        self.assertTrue('MonCS: ' in read_str)


if __name__ == "__main__":
    unittest.main()

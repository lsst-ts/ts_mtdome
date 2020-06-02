import asyncio
import asynctest
from asynctest.mock import CoroutineMock
import logging
import math

import yaml

from lsst.ts import Dome
from lsst.ts import salobj

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

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
        # Replace the determine_current_tai method with a mock method so that the current_tai value on the
        # mock_ctrl object can be set to make sure that the mock_ctrl object behaves as if that amount of
        # time has passed.
        self.mock_ctrl.determine_current_tai = CoroutineMock()
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

    async def prepare_amcs(
        self, initial_position, target_azimuth, target_rate,
    ):
        """Utility method for preparing the in initial state of AMCS for easier testing.

        Parameters
        ----------
        initial_position: `float`
            The initial position of AMCS in radians.
        target_azimuth: `float`
            The target azimuth for the AMCS rotation in radians.
        target_rate: `float`
            The target velocity at which to crawl once the target azimuth has been reached in rad/s.

        Returns
        -------

        """
        self.mock_ctrl.amcs.position_actual = initial_position
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n azRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai

    async def verify_amcs_moveAz(
        self, time_diff, expected_status, expected_position, crawl_velocity=0
    ):
        """Verify the expected status and position after the given time difference.

        If the expected status is MOVING, the expected position should exactly have been reached. If the
        expected status is CRAWLING, the expected position should have been reached as well but since the
        AMCS keeps moving, it will be greater or smaller depending on the speed.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `Dome.LlcStatus`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        crawl_velocity: `float`
            The expected velocity if the expected status is CRAWLING in rad/s.
        """
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], expected_status.value,
        )
        if expected_status == Dome.LlcStatus.MOVING:
            self.assertAlmostEqual(amcs_status["positionActual"], expected_position)
        elif expected_status == Dome.LlcStatus.CRAWLING:
            if crawl_velocity > 0:
                self.assertGreaterEqual(
                    amcs_status["positionActual"], expected_position
                )
            elif crawl_velocity < 0:
                self.assertLessEqual(amcs_status["positionActual"], expected_position)
            else:
                self.assertAlmostEqual(amcs_status["positionActual"], expected_position)

    async def test_moveAz_zero_pos_pos(self):
        # test moving the AMCS to an azimuth in positive direction starting from position 0 and ending in a
        # positive crawl velocity
        initial_position = 0
        target_azimuth = math.radians(10)
        target_rate = math.radians(0.1)
        await self.prepare_amcs(
            initial_position, target_azimuth, target_rate,
        )

        # Make the amcs rotate and check both status and position at the specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(1.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(3.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_rate
        )

    async def test_moveAz_zero_pos_neg(self):
        # test moving the AMCS to an azimuth in positive direction starting from position 0 and ending in a
        # negative crawl velocity
        initial_position = 0
        target_azimuth = math.radians(10)
        target_rate = math.radians(-0.1)
        await self.prepare_amcs(
            initial_position, target_azimuth, target_rate,
        )

        # Make the amcs rotate and check both status and position at the specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(1.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(3.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_rate
        )

    async def test_moveAz_zero_pos_zero(self):
        # test moving the AMCS to an azimuth in positive direction starting from position 0 and ending in a
        # stand still, i.e. a 0 crawl velocity
        initial_position = 0
        target_azimuth = math.radians(10)
        target_rate = 0
        await self.prepare_amcs(
            initial_position, target_azimuth, target_rate,
        )

        # Make the amcs rotate and check both status and position at the specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(1.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(3.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.STOPPED, math.radians(10.0), crawl_velocity=target_rate
        )

    async def test_moveAz_twenty_neg_pos(self):
        # test moving the AMCS to an azimuth in negative direction starting from position 20 degrees and
        # ending in a positive crawl velocity
        initial_position = math.radians(20)
        target_azimuth = math.radians(10)
        target_rate = math.radians(0.1)
        await self.prepare_amcs(
            initial_position, target_azimuth, target_rate,
        )

        # Make the amcs rotate and check both status and position at the specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(18.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(17.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_rate
        )

    async def test_moveAz_twenty_neg_neg(self):
        # test moving the AMCS to an azimuth in positive direction starting from position 20 degrees and
        # ending in a negative crawl velocity
        initial_position = math.radians(20)
        target_azimuth = math.radians(10)
        target_rate = math.radians(-0.1)
        await self.prepare_amcs(
            initial_position, target_azimuth, target_rate,
        )

        # Make the amcs rotate and check both status and position at the specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(18.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(17.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_rate
        )

    async def test_moveAz_zero_neg_zero(self):
        # test moving the AMCS to an azimuth in positive direction starting from position 0 and ending in a
        # stand still, i.e. a 0 crawl velocity
        initial_position = math.radians(20)
        target_azimuth = math.radians(10)
        target_rate = 0
        await self.prepare_amcs(
            initial_position, target_azimuth, target_rate,
        )

        # Make the amcs rotate and check both status and position at the specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(18.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(17.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.STOPPED, math.radians(10.0), crawl_velocity=target_rate
        )

    async def test_crawlAz(self):
        target_rate = math.radians(0.1)
        await self.write(f"crawlAz:\n azRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.CRAWLING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], math.radians(0.05),
        )
        self.assertLessEqual(
            amcs_status["positionActual"], math.radians(0.15),
        )

    async def test_stopAz(self):
        target_azimuth = math.radians(10)
        target_rate = math.radians(0.1)
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n azRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], math.radians(0.5),
        )
        self.assertLessEqual(
            amcs_status["positionActual"], math.radians(1.5),
        )

        await self.write("stopAz:\n")
        # Give some time to the mock device to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.short_timeout)

        await self.write("status:\n")
        self.data = await self.read()
        amcs_status = self.data[Dome.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], math.radians(1.0),
        )
        self.assertLessEqual(
            amcs_status["positionActual"], math.radians(1.7),
        )

    async def test_moveEl(self):
        target_elevation = math.radians(5)
        await self.write(f"moveEl:\n elevation: {target_elevation}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for easier control
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(1.5),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(2.0),
        )

        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(3.0),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(4.0),
        )

        # Give some time to the mock device to reach the commanded position.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            lwscs_status["positionActual"], math.radians(5.0),
        )

    async def test_stopEl(self):
        target_elevation = math.radians(5)
        await self.write(f"moveEl:\n elevation: {target_elevation}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for easier control
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(1.5),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(2.0),
        )

        await self.write("stopEl:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.short_timeout)

        # Give some time to the mock device to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(1.5),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(2.0),
        )

    async def test_stop(self):
        target_azimuth = math.radians(10)
        target_rate = math.radians(0.1)
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n azRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        target_elevation = math.radians(5)
        await self.write(f"moveEl:\n elevation: {target_elevation}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        louver_id = 5
        target_position = math.radians(90)
        await self.write(
            f"setLouver:\n id: {louver_id}\n position: {target_position}\n"
        )
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        await self.write("openShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write("stop:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock devices to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
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
        target_rate = math.radians(0.1)
        await self.write(f"crawlEl:\n elRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write("status:\n")
        self.data = await self.read()
        lwscs_status = self.data[Dome.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.CRAWLING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(0.05),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(0.15),
        )

    async def test_setLouver(self):
        louver_id = 5
        target_position = math.radians(90)
        await self.write(
            f"setLouver:\n id: {louver_id}\n position: {target_position}\n"
        )
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

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

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

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
        target_position = math.radians(90)
        await self.write(
            f"setLouver:\n id: {louver_id}\n position: {target_position}\n"
        )
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write("stopLouvers:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

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

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write("status:\n")
        self.data = await self.read()
        apscs_status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.OPEN.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], math.radians(90.0),
        )
        self.assertEqual(
            apscs_status["positionCmd"], math.radians(90.0),
        )

    async def test_closeShutter(self):
        await self.write("closeShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

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

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write("stopShutter:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write("status:\n")
        self.data = await self.read()
        apscs_status = self.data[Dome.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], math.radians(90.0),
        )
        self.assertEqual(
            apscs_status["positionCmd"], math.radians(90.0),
        )

    async def test_config(self):
        config = {
            Dome.LlcName.AMCS.value: {
                "jmax": math.radians(3.0),
                "amax": math.radians(0.75),
                "vmax": math.radians(1.5),
            },
            Dome.LlcName.LWSCS.value: {
                "jmax": math.radians(3.5),
                "amax": math.radians(0.875),
                "vmax": math.radians(1.75),
            },
        }
        await self.write(f"config:\n {config}\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

    async def test_park(self):
        target_azimuth = math.radians(1)
        target_rate = math.radians(0.1)
        await self.write(f"moveAz:\n azimuth: {target_azimuth}\n azRate: {target_rate}")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write("park:\n")
        self.data = await self.read()
        self.assertEqual(self.data["OK"]["Timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to park.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

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

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for easier control
        self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to set the temperature.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

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

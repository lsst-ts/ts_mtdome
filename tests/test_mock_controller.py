# This file is part of ts_MTDome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
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

import asyncio
import logging
import math
import unittest
from unittest.mock import AsyncMock

import numpy as np

from lsst.ts import MTDome

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

_CURRENT_TAI = 100001


class MockTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ctrl = None
        self.writer = None
        port = 0
        self.mock_ctrl = None
        self.data = None

        self.mock_ctrl = MTDome.MockMTDomeController(port=port)
        # Replace the determine_current_tai method with a mock method so that
        # the start_tai value on the mock_ctrl object can be set to make sure
        # that the mock_ctrl object  behaves as if that amount of time has
        # passed.
        self.mock_ctrl.determine_current_tai = AsyncMock()
        asyncio.create_task(self.mock_ctrl.start())
        await asyncio.sleep(1)
        # Request the assigned port from the mock controller.
        port = self.mock_ctrl.port

        rw_coro = asyncio.open_connection(host="127.0.0.1", port=port)
        self.reader, self.writer = await asyncio.wait_for(rw_coro, timeout=1)

        MTDome.encoding_tools.validation_raises_exception = True

        self.log = logging.getLogger("MockTestCase")

    async def read(self):
        """Utility function to read a string from the reader and unmarshal it

        Returns
        -------
        configuration_parameters : `dict`
            A dictionary with objects representing the string read.
        """
        read_bytes = await asyncio.wait_for(self.reader.readuntil(b"\r\n"), timeout=1)
        data = MTDome.encoding_tools.decode(read_bytes.decode())
        return data

    async def write(self, **data):
        """Utility function to write data to the writer.

        Parameters
        ----------
        data:
            The data to go write.
        """
        st = MTDome.encoding_tools.encode(**data)
        self.writer.write(st.encode() + b"\r\n")
        await self.writer.drain()

    async def asyncTearDown(self):
        if self.mock_ctrl:
            await asyncio.wait_for(self.mock_ctrl.stop(), 5)
        if self.writer:
            self.writer.close()

    async def test_too_many_command_parameters(self):
        # Temporarily disable validation exceptions for the unit test.
        # Validation of the commands should be done by the client and the
        # simulator has such validation built in.
        MTDome.encoding_tools.validation_raises_exception = False
        await self.write(
            command="moveAz",
            parameters={"position": 0.1, "velocity": 0.1, "acceleration": 0.1},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 3)
        self.assertEqual(self.data["timeout"], -1)

    async def prepare_amcs_move(
        self,
        start_position,
        target_position,
        target_velocity,
    ):
        """Utility method for preparing the initial state of AMCS for easier
        testing.

        Parameters
        ----------
        start_position: `float`
            The initial position of AMCS in radians.
        target_position: `float`
            The target position for the AMCS rotation in radians.
        target_velocity: `float`
            The target velocity at which to crawl once the target azimuth has
            been reached in rad/s.

        Returns
        -------

        """
        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.amcs.azimuth_motion._start_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.amcs.azimuth_motion._start_position = start_position
        await self.write(
            command="moveAz",
            parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.amcs.duration)

    async def verify_amcs_move(
        self, time_diff, expected_status, expected_position, crawl_velocity=0
    ):
        """Verify the expected status and position after the given time
        difference.

        If the expected status is MOVING, the expected position should exactly
        have been reached. If the expected status is CRAWLING, the expected
        position should have been  reached as well but since the AMCS keeps
        moving, it will be greater or smaller depending on the speed.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `MTDome.LlcMotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        crawl_velocity: `float`
            The expected velocity if the expected status is CRAWLING in rad/s.
        """
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["status"],
            expected_status.name,
        )
        if expected_status == MTDome.LlcMotionState.MOVING:
            self.assertAlmostEqual(amcs_status["positionActual"], expected_position, 3)
        elif expected_status == MTDome.LlcMotionState.CRAWLING:
            if crawl_velocity > 0:
                self.assertGreaterEqual(
                    amcs_status["positionActual"], expected_position
                )
            elif crawl_velocity < 0:
                self.assertLessEqual(amcs_status["positionActual"], expected_position)
            else:
                self.assertAlmostEqual(amcs_status["positionActual"], expected_position)

    async def test_moveAz_zero_pos_pos(self):
        # Test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a positive crawl velocity
        start_position = 0
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(1.5)
        )
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(3.0)
        )
        await self.verify_amcs_move(
            5.0,
            MTDome.LlcMotionState.CRAWLING,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_pos_neg(self):
        # Test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a negative crawl velocity
        start_position = 0
        target_position = math.radians(10)
        target_velocity = math.radians(-0.1)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(1.5)
        )
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(3.0)
        )
        await self.verify_amcs_move(
            5.0,
            MTDome.LlcMotionState.CRAWLING,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_pos_zero(self):
        # Test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a stand still, i.e. a 0 crawl velocity
        start_position = 0
        target_position = math.radians(10)
        target_velocity = 0
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(1.5)
        )
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(3.0)
        )
        await self.verify_amcs_move(
            5.0,
            MTDome.LlcMotionState.STOPPED,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_twenty_neg_pos(self):
        # Test moving the AMCS to a position in negative direction starting
        # from position 20 degrees and ending in a positive crawl velocity
        start_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(18.5)
        )
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(17.0)
        )
        await self.verify_amcs_move(
            5.0,
            MTDome.LlcMotionState.CRAWLING,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_twenty_neg_neg(self):
        # Test moving the AMCS to a position in positive direction starting
        # from position 20 degrees and ending in a negative crawl velocity
        start_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = math.radians(-0.1)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(18.5)
        )
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(17.0)
        )
        await self.verify_amcs_move(
            5.0,
            MTDome.LlcMotionState.CRAWLING,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_neg_zero(self):
        # Test moving the AMCS when an error occurs
        start_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = 0
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(18.5)
        )
        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(17.0)
        )
        await self.verify_amcs_move(
            5.0,
            MTDome.LlcMotionState.STOPPED,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_error(self):
        # Test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a stand still, i.e. a 0 crawl velocity
        start_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = 0
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Introduce an error. This will be improved once error codes have been
        # specified in a future Dome Software meeting.
        expected_error = [
            "Drive 1 temperature too high",
            "Drive 2 temperature too high",
        ]
        self.mock_ctrl.amcs.error = expected_error

        # Give some time to the mock device to move and theck the error status.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["error"],
            expected_error,
        )

    async def test_crawlAz(self):
        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        target_velocity = math.radians(0.1)
        await self.write(command="crawlAz", parameters={"velocity": target_velocity})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.amcs.duration)

        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["status"],
            MTDome.LlcMotionState.CRAWLING.name,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"],
            math.radians(0.05),
        )
        self.assertLessEqual(
            amcs_status["positionActual"],
            math.radians(0.15),
        )

    async def test_stopAz(self):
        start_position = math.radians(0)
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        await self.verify_amcs_move(
            1.0, MTDome.LlcMotionState.MOVING, math.radians(1.5)
        )

        await self.write(command="stopAz", parameters={})
        # Give some time to the mock device to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.amcs.duration)

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"],
            math.radians(1.7),
        )
        self.assertLessEqual(
            amcs_status["positionActual"],
            math.radians(1.9),
        )

    async def prepare_lwscs_move(self, start_position, target_position):
        """Utility method for preparing the initial state of LWSCS for easier
        testing.

        Parameters
        ----------
        start_position: `float`
            The initial position of LWSCS in radians.
        target_position: `float`
            The target position for the LWSCS rotation in radians.

        Returns
        -------

        """
        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.lwscs.elevation_motion._start_position = start_position
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.lwscs.duration)

    async def verify_lwscs_move(self, time_diff, expected_status, expected_position):
        """Verify the expected status and position after the given time
        difference.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `MTDome.LlcMotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        """
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[MTDome.llc_name.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"],
            expected_status.name,
        )
        self.assertAlmostEqual(lwscs_status["positionActual"], expected_position, 3)

    async def test_moveEl_zero_five(self):
        # Test moving the LWSCS from 0 to 5 degrees. This should succeed.
        start_position = 0
        target_position = math.radians(5)
        await self.prepare_lwscs_move(
            start_position=start_position, target_position=target_position
        )

        # Move EL and check the position.
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.MOVING,
            expected_position=math.radians(1.75),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.MOVING,
            expected_position=math.radians(3.5),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.STOPPED,
            expected_position=math.radians(5.0),
        )

    async def test_moveEl_five_zero(self):
        # Test moving the LWSCS from 5 to 0 degrees. This should succeed.
        start_position = math.radians(5)
        target_position = math.radians(0)
        await self.prepare_lwscs_move(
            start_position=start_position, target_position=target_position
        )

        # Move EL and check the position.
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.MOVING,
            expected_position=math.radians(3.25),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.MOVING,
            expected_position=math.radians(1.5),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.STOPPED,
            expected_position=math.radians(0),
        )

    async def test_moveEl_five_min_five(self):
        # Test moving the LWSCS from 5 to -5 degrees. This should NOT succeed.
        start_position = math.radians(5)
        target_position = math.radians(-5)
        # Sending the command should result in a ValueError. The exception
        # encountered here is a TimeoutError, which is why a much more general
        # Exception is caught.
        try:
            await self.prepare_lwscs_move(
                start_position=start_position, target_position=target_position
            )
            self.fail("A ValueError should have been raised.")
        except Exception:
            pass

    async def test_stopEl(self):
        start_position = 0
        target_position = math.radians(5)
        await self.prepare_lwscs_move(
            start_position=start_position, target_position=target_position
        )

        # Move EL and check the position and status.
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.MOVING,
            expected_position=math.radians(1.75),
        )

        # await self.write(command="stopEl", parameters={})
        # self.data = await self.read()
        # self.assertEqual(self.data["response"], 0)
        # self.assertEqual(self.data["timeout"], self.mock_ctrl.short_duration)

        # Move EL and check the position and status.
        await self.verify_lwscs_move(
            time_diff=0.1,
            expected_status=MTDome.LlcMotionState.MOVING,
            expected_position=math.radians(1.93),
        )

    async def prepare_all_llc(self):
        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai

        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.write(
            command="moveAz",
            parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.amcs.duration)

        target_position = math.radians(5)
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.lwscs.duration)

        louver_id = 5
        target_position = 100
        position = np.full(MTDome.mock_llc.lcs.NUM_LOUVERS, -1.0, dtype=float)
        position[louver_id] = target_position
        await self.write(
            command="setLouvers",
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

    async def test_stop(self):
        await self.prepare_all_llc()

        await self.write(command="stop", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Give some time to the mock devices to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            status["status"]["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )
        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.APSCS.value]
        self.assertEqual(
            status["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )
        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.LCS.value]
        self.assertEqual(
            status["status"],
            [MTDome.LlcMotionState.STOPPED.name] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.LWSCS.value]
        self.assertEqual(
            status["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )

    async def test_go_stationary(self):
        await self.prepare_all_llc()

        await self.write(command="goStationary", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Give some time to the mock devices to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            status["status"]["status"],
            MTDome.LlcMotionState.STATIONARY.name,
        )
        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.APSCS.value]
        self.assertEqual(
            status["status"],
            MTDome.LlcMotionState.STATIONARY.name,
        )
        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.LCS.value]
        self.assertEqual(
            status["status"],
            [MTDome.LlcMotionState.STATIONARY.name] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        status = self.data[MTDome.llc_name.LlcName.LWSCS.value]
        self.assertEqual(
            status["status"],
            MTDome.LlcMotionState.STATIONARY.name,
        )

    async def prepare_lwscs_crawl(self, start_position, target_velocity):
        """Utility method for preparing the initial state of LWSCS for easier
        testing.

        Parameters
        ----------
        start_position: `float`
            The initial position of LWSCS in radians.
        target_velocity: `float`
            The target velocity for the LWSCS rotation in radians/second.

        Returns
        -------

        """
        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.lwscs.elevation_motion._start_position = start_position
        await self.write(
            command="crawlEl",
            parameters={"velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.lwscs.duration)

    async def verify_lwscs_crawl(self, time_diff, expected_status, expected_position):
        """Verify the expected status and position after the given time
        difference.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `MTDome.LlcMotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        """
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[MTDome.llc_name.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"],
            expected_status.name,
        )
        self.assertAlmostEqual(lwscs_status["positionActual"], expected_position, 3)

    async def test_crawlEl(self):
        await self.prepare_lwscs_crawl(
            start_position=0, target_velocity=math.radians(0.1)
        )

        # Let EL crawl a little and check the position
        await self.verify_lwscs_crawl(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.CRAWLING,
            expected_position=math.radians(0.1),
        )
        await self.verify_lwscs_crawl(
            time_diff=1.0,
            expected_status=MTDome.LlcMotionState.CRAWLING,
            expected_position=math.radians(0.2),
        )

    async def prepare_louvers(self, louver_ids, target_positions):
        """Utility method for preparing the louvers for easier testing.

        Parameters
        ----------
        louver_ids: `list`
            A list with the IDs of the louvers to move.
        target_positions: `list`
            A list with the target positions of the louvers to move to.

        For each louver that will be moved, both an ID and a target position
        needs to be given. It is assumed that the indices of the IDs and the
        target positions are lined up.

        """
        position = np.full(MTDome.mock_llc.lcs.NUM_LOUVERS, -1.0, dtype=float)
        for index, louver_id in enumerate(louver_ids):
            position[louver_id] = target_positions[index]
        await self.write(
            command="setLouvers",
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

    async def verify_louvers(self, louver_ids, target_positions):
        """Utility method for verifying the positions of the louvers against
        the provided IDs and target
        positions.

        Parameters
        ----------
        louver_ids: `list`
            A list with the IDs of the louvers to move.
        target_positions: `list`
            A list with the target positions of the louvers to move to.

        For each louver that will be moved, both an ID and a target position
        needs to be given. It is assumed that the indices of the IDs and the
        target positions are lined up.

        """
        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()

        # See mock_llc.lcs for what the structure of lcs
        # looks like as well as for the meaning of LlcStatus.
        lcs_status = self.data[MTDome.llc_name.LlcName.LCS.value]
        for index, status in enumerate(lcs_status["status"]):
            if index in louver_ids:
                if target_positions[louver_ids.index(index)] > 0:
                    self.assertEqual(MTDome.LlcMotionState.OPEN.name, status)
                else:
                    self.assertEqual(MTDome.LlcMotionState.CLOSED.name, status)
            else:
                self.assertEqual(MTDome.LlcMotionState.CLOSED.name, status)
        for index, positionActual in enumerate(lcs_status["positionActual"]):
            if index in louver_ids:
                self.assertEqual(
                    target_positions[louver_ids.index(index)], positionActual
                )
            else:
                self.assertEqual(0, positionActual)
        for index, positionCommanded in enumerate(lcs_status["positionCommanded"]):
            if index in louver_ids:
                self.assertEqual(
                    target_positions[louver_ids.index(index)], positionCommanded
                )
            else:
                self.assertEqual(0, positionCommanded)

    async def test_setLouvers(self):
        # Open some of the louvers and verify that their status and positions
        # are as expected.
        louver_ids = [5, 6, 7, 8, 9, 10]
        target_positions = [100, 80, 70, 85, 25, 60]
        await self.prepare_louvers(louver_ids, target_positions)
        await self.verify_louvers(louver_ids, target_positions)

        # Now close them.
        louver_ids = [5, 6, 7, 8, 9, 10]
        target_positions = [0, 0, 0, 0, 0, 0]
        await self.prepare_louvers(louver_ids, target_positions)
        await self.verify_louvers(louver_ids, target_positions)

    async def test_closeLouvers(self):
        await self.write(command="closeLouvers", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[MTDome.llc_name.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"],
            [MTDome.LlcMotionState.CLOSED.name] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"],
            [0.0] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionCommanded"],
            [0.0] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )

    async def test_stopLouvers(self):
        louver_id = 5
        target_position = 100
        position = np.full(MTDome.mock_llc.lcs.NUM_LOUVERS, -1.0, dtype=float)
        position[louver_id] = target_position
        await self.write(
            command="setLouvers",
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="stopLouvers", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[MTDome.llc_name.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"],
            [MTDome.LlcMotionState.STOPPED.name] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"],
            [0.0] * louver_id
            + [target_position]
            + [0.0] * (MTDome.mock_llc.lcs.NUM_LOUVERS - louver_id - 1),
        )
        self.assertEqual(
            lcs_status["positionCommanded"],
            [0.0] * louver_id
            + [target_position]
            + [0.0] * (MTDome.mock_llc.lcs.NUM_LOUVERS - louver_id - 1),
        )

    async def test_openShutter(self):
        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[MTDome.llc_name.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"],
            MTDome.LlcMotionState.OPEN.name,
        )
        self.assertEqual(
            apscs_status["positionActual"],
            [100.0, 100.0],
        )
        self.assertEqual(
            apscs_status["positionCommanded"],
            100.0,
        )

    async def test_closeShutter(self):
        await self.write(command="closeShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[MTDome.llc_name.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"],
            MTDome.LlcMotionState.CLOSED.name,
        )
        self.assertEqual(
            apscs_status["positionActual"],
            [0.0, 0.0],
        )
        self.assertEqual(
            apscs_status["positionCommanded"],
            0.0,
        )

    async def test_stopShutter(self):
        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="stopShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[MTDome.llc_name.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )
        self.assertEqual(
            apscs_status["positionActual"],
            [100.0, 100.0],
        )
        self.assertEqual(
            apscs_status["positionCommanded"],
            100.0,
        )

    async def test_config(self):
        # All AMCS values within the limits.
        amcs_jmax = math.radians(2.0)
        amcs_amax = math.radians(0.5)
        amcs_vmax = math.radians(0.375)

        parameters = {
            "system": MTDome.llc_name.LlcName.AMCS.value,
            "settings": [
                {"target": "jmax", "setting": [amcs_jmax]},
                {"target": "amax", "setting": [amcs_amax]},
                {"target": "vmax", "setting": [amcs_vmax]},
            ],
        }
        await self.write(command="config", parameters=parameters)
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        self.assertEqual(self.mock_ctrl.amcs.amcs_limits.jmax, amcs_jmax)
        self.assertEqual(self.mock_ctrl.amcs.amcs_limits.amax, amcs_amax)
        self.assertEqual(self.mock_ctrl.amcs.amcs_limits.vmax, amcs_vmax)

        # All LWSCS values within the limits.
        lwscs_jmax = math.radians(2.5)
        lwscs_amax = math.radians(0.75)
        lwscs_vmax = math.radians(0.5)

        parameters = {
            "system": MTDome.llc_name.LlcName.LWSCS.value,
            "settings": [
                {"target": "jmax", "setting": [lwscs_jmax]},
                {"target": "amax", "setting": [lwscs_amax]},
                {"target": "vmax", "setting": [lwscs_vmax]},
            ],
        }
        await self.write(command="config", parameters=parameters)
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        self.assertEqual(self.mock_ctrl.lwscs.lwscs_limits.jmax, lwscs_jmax)
        self.assertEqual(self.mock_ctrl.lwscs.lwscs_limits.amax, lwscs_amax)
        self.assertEqual(self.mock_ctrl.lwscs.lwscs_limits.vmax, lwscs_vmax)

    async def test_park(self):
        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        target_position = math.radians(1)
        target_velocity = math.radians(0.1)
        await self.write(
            command="moveAz",
            parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.amcs.duration)

        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="park", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.amcs.duration)

        # Give some time to the mock device to park.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 5.0

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["status"],
            MTDome.LlcMotionState.PARKED.name,
        )
        self.assertEqual(
            amcs_status["positionActual"],
            MTDome.mock_llc.amcs.PARK_POSITION,
        )
        self.assertEqual(
            amcs_status["positionCommanded"],
            MTDome.mock_llc.amcs.PARK_POSITION,
        )

    async def test_setTemperature(self):
        temperature = 10.0
        await self.write(
            command="setTemperature", parameters={"temperature": temperature}
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to set the temperature.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusThCS", parameters={})
        self.data = await self.read()
        thcs_status = self.data[MTDome.llc_name.LlcName.THCS.value]
        self.assertEqual(
            thcs_status["status"],
            MTDome.LlcMotionState.OPEN.name,
        )
        self.assertEqual(
            thcs_status["temperature"],
            [temperature] * MTDome.mock_llc.thcs.NUM_THERMO_SENSORS,
        )

    async def test_inflate(self):
        # Make sure that the inflate status is set to OFF
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["inflate"],
            MTDome.OnOff.OFF.value,
        )
        await self.write(
            command="inflate", parameters={"action": MTDome.OnOff.ON.value}
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)
        self.assertEqual(self.mock_ctrl.amcs.seal_inflated, MTDome.OnOff.ON)
        # Also check that the inflate status is set in the AMCS status.
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["inflate"],
            MTDome.OnOff.ON.value,
        )

    async def test_fans(self):
        # Make sure that the fans status is set to OFF
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["fans"],
            MTDome.OnOff.OFF.value,
        )
        await self.write(command="fans", parameters={"action": MTDome.OnOff.ON.value})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_duration)
        self.assertEqual(self.mock_ctrl.amcs.fans_enabled, MTDome.OnOff.ON)
        # Also check that the fans status is set in the AMCS status.
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["fans"],
            MTDome.OnOff.ON.value,
        )

    async def test_status(self):
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[MTDome.llc_name.LlcName.AMCS.value]
        self.assertEqual(
            amcs_status["status"]["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )
        self.assertEqual(
            amcs_status["positionActual"],
            0,
        )

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[MTDome.llc_name.LlcName.APSCS.value]
        self.assertEqual(
            apscs_status["status"],
            MTDome.LlcMotionState.CLOSED.name,
        )
        self.assertEqual(
            apscs_status["positionActual"],
            [0.0, 0.0],
        )

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[MTDome.llc_name.LlcName.LCS.value]
        self.assertEqual(
            lcs_status["status"],
            [MTDome.LlcMotionState.CLOSED.name] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"],
            [0.0] * MTDome.mock_llc.lcs.NUM_LOUVERS,
        )

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[MTDome.llc_name.LlcName.LWSCS.value]
        self.assertEqual(
            lwscs_status["status"],
            MTDome.LlcMotionState.STOPPED.name,
        )
        self.assertEqual(
            lwscs_status["positionActual"],
            0,
        )

        await self.write(command="statusMonCS", parameters={})
        self.data = await self.read()
        moncs_status = self.data[MTDome.llc_name.LlcName.MONCS.value]
        self.assertEqual(
            moncs_status["status"],
            MTDome.LlcMotionState.CLOSED.name,
        )
        self.assertEqual(
            moncs_status["data"],
            [0.0] * MTDome.mock_llc.moncs.NUM_MON_SENSORS,
        )

        await self.write(command="statusThCS", parameters={})
        self.data = await self.read()
        thcs_status = self.data[MTDome.llc_name.LlcName.THCS.value]
        self.assertEqual(
            thcs_status["status"],
            MTDome.LlcMotionState.CLOSED.name,
        )
        self.assertEqual(
            thcs_status["temperature"],
            [0.0] * MTDome.mock_llc.thcs.NUM_THERMO_SENSORS,
        )

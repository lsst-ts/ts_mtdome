# This file is part of ts_Dome.
#
# Developed for the LSST Data Management System.
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
import asynctest
from asynctest.mock import CoroutineMock
import logging
import math

import numpy as np

from lsst.ts import Dome
from lsst.ts import salobj
from lsst.ts.Dome.llc_name import LlcName

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG)

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
        # Replace the determine_current_tai method with a mock method so that
        # the current_tai value on the mock_ctrl object can be set to make sure
        # that the mock_ctrl object  behaves as if that amount of time has
        # passed.
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
        data = Dome.encoding_tools.decode(read_bytes.decode())
        return data

    async def write(self, **data):
        """Utility function to write data to the writer.

        Parameters
        ----------
        data:
            The data to go write.
        """
        st = Dome.encoding_tools.encode(**data)
        self.writer.write(st.encode() + b"\r\n")
        await self.writer.drain()

    async def tearDown(self):
        if self.mock_ctrl:
            await asyncio.wait_for(self.mock_ctrl.stop(), 5)
        if self.writer:
            self.writer.close()

    async def test_command_does_not_exist(self):
        await self.write(command="non-existent_command", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 2)
        self.assertEqual(self.data["timeout"], -1)

    async def test_missing_command_parameter(self):
        await self.write(command="moveAz", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 3)
        self.assertEqual(self.data["timeout"], -1)

    async def test_too_many_command_parameters(self):
        await self.write(
            command="moveAz", parameters={"position": 0.1, "velocity": 0.1, "acceleration": 0.1},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 3)
        self.assertEqual(self.data["timeout"], -1)

    async def prepare_amcs(
        self, initial_position, target_position, target_velocity,
    ):
        """Utility method for preparing the initial state of AMCS for easier
        testing.

        Parameters
        ----------
        initial_position: `float`
            The initial position of AMCS in radians.
        target_position: `float`
            The target position for the AMCS rotation in radians.
        target_velocity: `float`
            The target velocity at which to crawl once the target azimuth has
            been reached in rad/s.

        Returns
        -------

        """
        self.mock_ctrl.amcs.position_actual = initial_position
        await self.write(
            command="moveAz", parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai

    async def verify_amcs_moveAz(self, time_diff, expected_status, expected_position, crawl_velocity=0):
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
        expected_status: `Dome.LlcStatus`
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
        amcs_status = self.data[LlcName.AMCS.value][0]
        self.assertEqual(
            amcs_status["status"], expected_status.value,
        )
        if expected_status == Dome.LlcStatus.MOVING:
            self.assertAlmostEqual(amcs_status["positionActual"], expected_position)
        elif expected_status == Dome.LlcStatus.CRAWLING:
            if crawl_velocity > 0:
                self.assertGreaterEqual(amcs_status["positionActual"], expected_position)
            elif crawl_velocity < 0:
                self.assertLessEqual(amcs_status["positionActual"], expected_position)
            else:
                self.assertAlmostEqual(amcs_status["positionActual"], expected_position)

    async def test_moveAz_zero_pos_pos(self):
        # test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a positive crawl velocity
        initial_position = 0
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.prepare_amcs(
            initial_position, target_position, target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(1.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(3.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_pos_neg(self):
        # test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a negative crawl velocity
        initial_position = 0
        target_position = math.radians(10)
        target_velocity = math.radians(-0.1)
        await self.prepare_amcs(
            initial_position, target_position, target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(1.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(3.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_pos_zero(self):
        # test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a stand still, i.e. a 0 crawl velocity
        initial_position = 0
        target_position = math.radians(10)
        target_velocity = 0
        await self.prepare_amcs(
            initial_position, target_position, target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(1.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(3.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.STOPPED, math.radians(10.0), crawl_velocity=target_velocity,
        )

    async def test_moveAz_twenty_neg_pos(self):
        # test moving the AMCS to a position in negative direction starting
        # from position 20 degrees and ending in a positive crawl velocity
        initial_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.prepare_amcs(
            initial_position, target_position, target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(18.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(17.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_velocity,
        )

    async def test_moveAz_twenty_neg_neg(self):
        # test moving the AMCS to a position in positive direction starting
        # from position 20 degrees and ending in a negative crawl velocity
        initial_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = math.radians(-0.1)
        await self.prepare_amcs(
            initial_position, target_position, target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(18.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(17.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.CRAWLING, math.radians(10.0), crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_neg_zero(self):
        # test moving the AMCS to a position in positive direction starting
        # from position 0 and ending in a stand still, i.e. a 0 crawl velocity
        initial_position = math.radians(20)
        target_position = math.radians(10)
        target_velocity = 0
        await self.prepare_amcs(
            initial_position, target_position, target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(18.5))
        await self.verify_amcs_moveAz(1.0, Dome.LlcStatus.MOVING, math.radians(17.0))
        await self.verify_amcs_moveAz(
            5.0, Dome.LlcStatus.STOPPED, math.radians(10.0), crawl_velocity=target_velocity,
        )

    async def test_crawlAz(self):
        target_velocity = math.radians(0.1)
        await self.write(command="crawlAz", parameters={"velocity": target_velocity})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[LlcName.AMCS.value][0]
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
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.write(
            command="moveAz", parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[LlcName.AMCS.value][0]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            amcs_status["positionActual"], math.radians(0.5),
        )
        self.assertLessEqual(
            amcs_status["positionActual"], math.radians(1.5),
        )

        await self.write(command="stopAz", parameters={})
        # Give some time to the mock device to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.short_timeout)

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[LlcName.AMCS.value][0]
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
        target_position = math.radians(5)
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
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
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
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
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            lwscs_status["positionActual"], math.radians(5.0),
        )

    async def test_stopEl(self):
        target_position = math.radians(5)
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.MOVING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(1.5),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(2.0),
        )

        await self.write(command="stopEl", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.short_timeout)

        # Give some time to the mock device to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
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
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.write(
            command="moveAz", parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        target_position = math.radians(5)
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        louver_id = 5
        target_position = 100
        position = np.full(_NUM_LOUVERS, -1.0, dtype=float)
        position[louver_id] = target_position
        await self.write(
            command="setLouvers", parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="stop", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock devices to stop moving.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        status = self.data[LlcName.AMCS.value][0]
        self.assertEqual(
            status["status"], Dome.LlcStatus.STOPPED.value,
        )
        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        status = self.data[LlcName.APSCS.value][0]
        self.assertEqual(
            status["status"], Dome.LlcStatus.STOPPED.value,
        )
        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        status = self.data[LlcName.LCS.value][0]
        self.assertEqual(
            status["status"], [Dome.LlcStatus.STOPPED.value] * _NUM_LOUVERS,
        )
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        status = self.data[LlcName.LWSCS.value][0]
        self.assertEqual(
            status["status"], Dome.LlcStatus.STOPPED.value,
        )

    async def test_crawlEl(self):
        target_velocity = math.radians(0.1)
        await self.write(command="crawlEl", parameters={"velocity": target_velocity})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lwscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.CRAWLING.value,
        )
        self.assertGreaterEqual(
            lwscs_status["positionActual"], math.radians(0.05),
        )
        self.assertLessEqual(
            lwscs_status["positionActual"], math.radians(0.15),
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
        position = np.full(_NUM_LOUVERS, -1.0, dtype=float)
        for index, louver_id in enumerate(louver_ids):
            position[louver_id] = target_positions[index]
        await self.write(
            command="setLouvers", parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
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

        # See mock_llc_statuses.lcs_status for what the structure of lcs_status
        # looks like as well as for the meaning of LlcStatus.
        lcs_status = self.data[LlcName.LCS.value][0]
        for index, status in enumerate(lcs_status["status"]):
            if index in louver_ids:
                if target_positions[louver_ids.index(index)] > 0:
                    self.assertEqual(Dome.LlcStatus.OPEN.value, status)
                else:
                    self.assertEqual(Dome.LlcStatus.CLOSED.value, status)
            else:
                self.assertEqual(Dome.LlcStatus.CLOSED.value, status)
        for index, positionActual in enumerate(lcs_status["positionActual"]):
            if index in louver_ids:
                self.assertEqual(target_positions[louver_ids.index(index)], positionActual)
            else:
                self.assertEqual(0, positionActual)
        for index, positionCommanded in enumerate(lcs_status["positionCommanded"]):
            if index in louver_ids:
                self.assertEqual(target_positions[louver_ids.index(index)], positionCommanded)
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
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[LlcName.LCS.value][0]
        self.assertEqual(
            lcs_status["status"], [Dome.LlcStatus.CLOSED.value] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"], [0.0] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionCommanded"], [0.0] * _NUM_LOUVERS,
        )

    async def test_stopLouvers(self):
        louver_id = 5
        target_position = 100
        position = np.full(_NUM_LOUVERS, -1.0, dtype=float)
        position[louver_id] = target_position
        await self.write(
            command="setLouvers", parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="stopLouvers", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[LlcName.LCS.value][0]
        self.assertEqual(
            lcs_status["status"], [Dome.LlcStatus.STOPPED.value] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"],
            [0.0] * louver_id + [target_position] + [0.0] * (_NUM_LOUVERS - louver_id - 1),
        )
        self.assertEqual(
            lcs_status["positionCommanded"],
            [0.0] * louver_id + [target_position] + [0.0] * (_NUM_LOUVERS - louver_id - 1),
        )

    async def test_openShutter(self):
        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[LlcName.APSCS.value][0]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.OPEN.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 100.0,
        )
        self.assertEqual(
            apscs_status["positionCommanded"], 100.0,
        )

    async def test_closeShutter(self):
        await self.write(command="closeShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[LlcName.APSCS.value][0]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.CLOSED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 0.0,
        )
        self.assertEqual(
            apscs_status["positionCommanded"], 0.0,
        )

    async def test_stopShutter(self):
        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="stopShutter", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[LlcName.APSCS.value][0]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 100.0,
        )
        self.assertEqual(
            apscs_status["positionCommanded"], 100.0,
        )

    async def test_config(self):
        amcs_jmax = math.radians(2.0)
        amcs_amax = math.radians(0.5)
        amcs_vmax = math.radians(0.375)
        lwscs_jmax = math.radians(2.5)
        lwscs_amax = math.radians(0.75)
        lwscs_vmax = math.radians(0.5)

        parameters = {
            "system": LlcName.AMCS.value,
            "settings": [{"jmax": [amcs_jmax], "amax": [amcs_amax], "vmax": [amcs_vmax]}],
        }
        await self.write(command="config", parameters=parameters)
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        parameters = {
            "system": LlcName.LWSCS.value,
            "settings": [{"jmax": [lwscs_jmax], "amax": [lwscs_amax], "vmax": [lwscs_vmax]}],
        }
        await self.write(command="config", parameters=parameters)
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        self.assertEqual(self.mock_ctrl.amcs.amcs_limits.jmax, amcs_jmax)
        self.assertEqual(self.mock_ctrl.amcs.amcs_limits.amax, amcs_amax)
        self.assertEqual(self.mock_ctrl.amcs.amcs_limits.vmax, amcs_vmax)
        self.assertEqual(self.mock_ctrl.lwscs.lwscs_limits.jmax, lwscs_jmax)
        self.assertEqual(self.mock_ctrl.lwscs.lwscs_limits.amax, lwscs_amax)
        self.assertEqual(self.mock_ctrl.lwscs.lwscs_limits.vmax, lwscs_vmax)

    async def test_park(self):
        target_position = math.radians(1)
        target_velocity = math.radians(0.1)
        await self.write(
            command="moveAz", parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="park", parameters={})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Give some time to the mock device to park.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[LlcName.AMCS.value][0]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.PARKED.value,
        )
        self.assertEqual(
            amcs_status["positionActual"], 0,
        )
        self.assertEqual(
            amcs_status["positionCommanded"], 0,
        )

    async def test_setTemperature(self):
        temperature = 10.0
        await self.write(command="setTemperature", parameters={"temperature": temperature})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = salobj.current_tai()
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to set the temperature.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusThCS", parameters={})
        self.data = await self.read()
        thcs_status = self.data[LlcName.THCS.value][0]
        self.assertEqual(
            thcs_status["status"], Dome.LlcStatus.ENABLED.value,
        )
        self.assertEqual(
            thcs_status["temperature"], [temperature] * _NUM_THERMO_SENSORS,
        )

    async def test_inflate(self):
        await self.write(command="inflate", parameters={"action": Dome.OnOff.ON.name})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)
        # The status of the inflatable seal is not part of the output of amcs
        # status so this is the only way to check the result of executing the
        # inflate command
        self.assertEqual(self.mock_ctrl.amcs.seal_inflated, Dome.OnOff.ON)

    async def test_fans(self):
        await self.write(command="fans", parameters={"action": Dome.OnOff.ON.name})
        self.data = await self.read()
        self.assertEqual(self.data["response"], 0)
        self.assertEqual(self.data["timeout"], self.mock_ctrl.long_timeout)
        # The status of the fans is not part of the output of amcs status so
        # this is the only way to check the result of executing the fans
        # command
        self.assertEqual(self.mock_ctrl.amcs.fans_enabled, Dome.OnOff.ON)

    async def test_status(self):
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[LlcName.AMCS.value][0]
        self.assertEqual(
            amcs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            amcs_status["positionActual"], 0,
        )

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[LlcName.APSCS.value][0]
        self.assertEqual(
            apscs_status["status"], Dome.LlcStatus.CLOSED.value,
        )
        self.assertEqual(
            apscs_status["positionActual"], 0,
        )

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[LlcName.LCS.value][0]
        self.assertEqual(
            lcs_status["status"], [Dome.LlcStatus.CLOSED.value] * _NUM_LOUVERS,
        )
        self.assertEqual(
            lcs_status["positionActual"], [0.0] * _NUM_LOUVERS,
        )

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[LlcName.LWSCS.value][0]
        self.assertEqual(
            lwscs_status["status"], Dome.LlcStatus.STOPPED.value,
        )
        self.assertEqual(
            lwscs_status["positionActual"], 0,
        )

        await self.write(command="statusMonCS", parameters={})
        self.data = await self.read()
        moncs_status = self.data[LlcName.MONCS.value][0]
        self.assertEqual(
            moncs_status["status"], Dome.LlcStatus.DISABLED.value,
        )
        self.assertEqual(
            moncs_status["data"], [0.0] * _NUM_MON_SENSORS,
        )

        await self.write(command="statusThCS", parameters={})
        self.data = await self.read()
        thcs_status = self.data[LlcName.THCS.value][0]
        self.assertEqual(
            thcs_status["status"], Dome.LlcStatus.DISABLED.value,
        )
        self.assertEqual(
            thcs_status["temperature"], [0.0] * _NUM_THERMO_SENSORS,
        )


if __name__ == "__main__":
    asynctest.main()

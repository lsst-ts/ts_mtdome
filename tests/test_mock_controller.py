# This file is part of ts_mtdome.
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
import typing
import unittest

import numpy as np
import pytest

from lsst.ts import mtdome
from lsst.ts.idl.enums.MTDome import OperationalMode

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

_CURRENT_TAI = 100001
START_MOTORS_ADD_DURATION = 5.5

# Default timeout for reads
DEFAULT_TIMEOUT = 1.0
# Long timeout in case of a mock network issue
SLOW_NETWORK_TIMEOUT = mtdome.MockMTDomeController.SLOW_NETWORK_SLEEP + 1.0


class MockTestCase(unittest.IsolatedAsyncioTestCase):
    async def determine_current_tai(self) -> None:
        pass

    async def asyncSetUp(self) -> None:
        self.ctrl = None
        self.writer = None
        port = 0
        self.data: typing.Optional[dict] = None

        self.mock_ctrl = mtdome.MockMTDomeController(port=port)
        # Replace the determine_current_tai method with a mock method so that
        # the start_tai value on the mock_ctrl object can be set to make sure
        # that the mock_ctrl object  behaves as if that amount of time has
        # passed.
        self.mock_ctrl.determine_current_tai = self.determine_current_tai
        asyncio.create_task(self.mock_ctrl.start())
        await asyncio.sleep(1)
        # Request the assigned port from the mock controller.
        port = self.mock_ctrl.port

        rw_coro = asyncio.open_connection(host="127.0.0.1", port=port)
        self.reader, self.writer = await asyncio.wait_for(rw_coro, timeout=1)

        mtdome.encoding_tools.validation_raises_exception = True

        self.log = logging.getLogger("MockTestCase")

    async def read(self, timeout: float = DEFAULT_TIMEOUT) -> dict:
        """Utility function to read a string from the reader and unmarshal it.

        Parameters
        ----------
        timeout : float, optional
            The timeout to use; default to 1 [s].

        Returns
        -------
        data : `dict`
            A dictionary with objects representing the string read.
        """
        read_bytes = await asyncio.wait_for(
            self.reader.readuntil(b"\r\n"), timeout=timeout
        )
        data = mtdome.encoding_tools.decode(read_bytes.decode())
        return data

    async def write(self, **data: typing.Any) -> None:
        """Utility function to write data to the writer.

        Parameters
        ----------
        data:
            The data to go write.
        """
        st = mtdome.encoding_tools.encode(**data)
        assert self.writer is not None
        self.writer.write(st.encode() + b"\r\n")
        await self.writer.drain()

    async def asyncTearDown(self) -> None:
        if self.mock_ctrl:
            await asyncio.wait_for(self.mock_ctrl.stop(), 5)
        if self.writer:
            self.writer.close()

    async def test_too_many_command_parameters(self) -> None:
        # Temporarily disable validation exceptions for the unit test.
        # Validation of the commands should be done by the client and the
        # simulator has such validation built in.
        mtdome.encoding_tools.validation_raises_exception = False
        await self.write(
            command="moveAz",
            parameters={"position": 0.1, "velocity": 0.1, "acceleration": 0.1},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.COMMAND_REJECTED
        assert self.data["timeout"] == -1

    async def prepare_amcs_move(
        self,
        start_position: float,
        target_position: float,
        target_velocity: float,
    ) -> None:
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
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.amcs.azimuth_motion._start_tai = self.mock_ctrl.current_tai
        self.mock_ctrl.amcs.azimuth_motion._start_position = start_position
        await self.write(
            command="moveAz",
            parameters={"position": target_position, "velocity": target_velocity},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.amcs.end_tai - _CURRENT_TAI
        )

    async def verify_amcs_move(
        self,
        time_diff: float,
        expected_status: mtdome.LlcMotionState,
        expected_position: float,
        crawl_velocity: float = 0.0,
    ) -> None:
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
        expected_status: `mtdome.LlcMotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        crawl_velocity: `float`
            The expected velocity if the expected status is CRAWLING in rad/s.
        """
        # Give some time to the mock device to move.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == expected_status.name
        assert amcs_status["positionActual"] == pytest.approx(
            expected_position, rel=1e-3
        )

    async def test_moveAz_zero_pos_pos(self) -> None:
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(1.5),
        )
        await self.verify_amcs_move(
            1.0, mtdome.LlcMotionState.MOVING, math.radians(3.0)
        )
        await self.verify_amcs_move(
            5.0,
            mtdome.LlcMotionState.CRAWLING,
            math.radians(10.03),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_pos_neg(self) -> None:
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(1.5),
        )
        await self.verify_amcs_move(
            1.0, mtdome.LlcMotionState.MOVING, math.radians(3.0)
        )
        await self.verify_amcs_move(
            5.0,
            mtdome.LlcMotionState.CRAWLING,
            math.radians(9.97),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_pos_zero(self) -> None:
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(1.5),
        )
        await self.verify_amcs_move(
            1.0, mtdome.LlcMotionState.MOVING, math.radians(3.0)
        )
        await self.verify_amcs_move(
            5.0,
            mtdome.LlcMotionState.STOPPED,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_twenty_neg_pos(self) -> None:
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(18.5),
        )
        await self.verify_amcs_move(
            1.0, mtdome.LlcMotionState.MOVING, math.radians(17.0)
        )
        await self.verify_amcs_move(
            5.0,
            mtdome.LlcMotionState.CRAWLING,
            math.radians(10.03),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_twenty_neg_neg(self) -> None:
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(18.5),
        )
        await self.verify_amcs_move(
            1.0, mtdome.LlcMotionState.MOVING, math.radians(17.0)
        )
        await self.verify_amcs_move(
            5.0,
            mtdome.LlcMotionState.CRAWLING,
            math.radians(9.97),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_zero_neg_zero(self) -> None:
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(18.5),
        )
        await self.verify_amcs_move(
            1.0, mtdome.LlcMotionState.MOVING, math.radians(17.0)
        )
        await self.verify_amcs_move(
            5.0,
            mtdome.LlcMotionState.STOPPED,
            math.radians(10.0),
            crawl_velocity=target_velocity,
        )

    async def test_moveAz_error(self) -> None:
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

        # Introduce errors. This will be improved once error codes have been
        # specified in a future Dome Software meeting.
        expected_messages = [
            {"code": 100, "description": "Drive 1 temperature too high"},
            {"code": 100, "description": "Drive 2 temperature too high"},
        ]
        assert self.mock_ctrl is not None
        self.mock_ctrl.amcs.messages = expected_messages

        # Give some time to the mock device to move and theck the error status.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["messages"] == expected_messages

    async def test_crawlAz(self) -> None:
        # Set the TAI time in the mock controller for easier control
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device status TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
        target_velocity = math.radians(0.1)
        await self.write(command="crawlAz", parameters={"velocity": target_velocity})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.amcs.end_tai - _CURRENT_TAI
        )

        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = (
            self.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 1.0
        )

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == mtdome.LlcMotionState.CRAWLING.name
        assert amcs_status["positionActual"] >= math.radians(0.05)
        assert amcs_status["positionActual"] <= math.radians(0.15)

    async def test_stopAz(self) -> None:
        start_position = math.radians(0)
        target_position = math.radians(10)
        target_velocity = math.radians(0.1)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        await self.verify_amcs_move(
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(1.5),
        )

        await self.write(command="stopAz", parameters={})
        # Give some time to the mock device to stop moving.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == 0.0

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == mtdome.LlcMotionState.STOPPED.name
        assert amcs_status["positionActual"] >= math.radians(1.7)
        assert amcs_status["positionActual"] <= math.radians(1.9)

    async def prepare_lwscs_move(
        self, start_position: float, target_position: float
    ) -> None:
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
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.lwscs.elevation_motion._start_position = start_position
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.lwscs.end_tai - _CURRENT_TAI
        )

    async def verify_lwscs_move(
        self,
        time_diff: float,
        expected_status: mtdome.LlcMotionState,
        expected_position: float,
    ) -> None:
        """Verify the expected status and position after the given time
        difference.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `mtdome.LlcMotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        """
        # Give some time to the mock device to move.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
        assert lwscs_status["status"]["status"] == expected_status.name
        assert lwscs_status["positionActual"] == pytest.approx(expected_position, 3)

    async def test_moveEl_zero_five(self) -> None:
        # Test moving the LWSCS from 0 to 5 degrees. This should succeed.
        start_position = 0
        target_position = math.radians(5)
        await self.prepare_lwscs_move(
            start_position=start_position, target_position=target_position
        )

        # Move EL and check the position.
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.MOVING,
            expected_position=math.radians(1.75),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.MOVING,
            expected_position=math.radians(3.5),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.STOPPED,
            expected_position=math.radians(5.0),
        )

    async def test_moveEl_five_zero(self) -> None:
        # Test moving the LWSCS from 5 to 0 degrees. This should succeed.
        start_position = math.radians(5)
        target_position = math.radians(0)
        await self.prepare_lwscs_move(
            start_position=start_position, target_position=target_position
        )

        # Move EL and check the position.
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.MOVING,
            expected_position=math.radians(3.25),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.MOVING,
            expected_position=math.radians(1.5),
        )
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.STOPPED,
            expected_position=math.radians(0),
        )

    async def test_moveEl_five_min_five(self) -> None:
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

    async def test_stopEl(self) -> None:
        start_position = 0
        target_position = math.radians(5)
        await self.prepare_lwscs_move(
            start_position=start_position, target_position=target_position
        )

        # Move EL and check the position and status.
        await self.verify_lwscs_move(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.MOVING,
            expected_position=math.radians(1.75),
        )

        await self.write(command="stopEl", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == 0.0

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
        assert lwscs_status["status"]["status"] == mtdome.LlcMotionState.STOPPED.name
        assert lwscs_status["positionActual"] >= math.radians(1.7)
        assert lwscs_status["positionActual"] <= math.radians(1.9)

    async def prepare_all_llc(self) -> None:
        # Set the TAI time in the mock controller for easier control
        assert self.mock_ctrl is not None
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
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.amcs.end_tai - _CURRENT_TAI
        )

        target_position = math.radians(5)
        await self.write(command="moveEl", parameters={"position": target_position})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == self.mock_ctrl.lwscs.end_tai - _CURRENT_TAI

        louver_id = 5
        target_position = 100
        position = np.full(mtdome.mock_llc.NUM_LOUVERS, -1.0, dtype=float)
        position[louver_id] = target_position
        await self.write(
            command="setLouvers",
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Give some time to the mock device to move.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 1.0

    async def prepare_lwscs_crawl(
        self, start_position: float, target_velocity: float
    ) -> None:
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
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.lwscs.elevation_motion._start_position = start_position
        await self.write(
            command="crawlEl",
            parameters={"velocity": target_velocity},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == self.mock_ctrl.lwscs.end_tai - _CURRENT_TAI

    async def verify_lwscs_crawl(
        self,
        time_diff: float,
        expected_status: mtdome.LlcMotionState,
        expected_position: float,
    ) -> None:
        """Verify the expected status and position after the given time
        difference.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `mtdome.LlcMotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        """
        # Give some time to the mock device to move.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
        assert lwscs_status["status"]["status"] == expected_status.name
        assert lwscs_status["positionActual"] == pytest.approx(expected_position, 3)

    async def test_crawlEl(self) -> None:
        await self.prepare_lwscs_crawl(
            start_position=0, target_velocity=math.radians(0.1)
        )

        # Let EL crawl a little and check the position
        await self.verify_lwscs_crawl(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.CRAWLING,
            expected_position=math.radians(0.1),
        )
        await self.verify_lwscs_crawl(
            time_diff=1.0,
            expected_status=mtdome.LlcMotionState.CRAWLING,
            expected_position=math.radians(0.2),
        )

    async def prepare_louvers(
        self, louver_ids: list[int], target_positions: list[float]
    ) -> None:
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
        position = np.full(mtdome.mock_llc.NUM_LOUVERS, -1.0, dtype=float)
        for index, louver_id in enumerate(louver_ids):
            position[louver_id] = target_positions[index]
        await self.write(
            command="setLouvers",
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

    async def verify_louvers(
        self, louver_ids: list[int], target_positions: list[float]
    ) -> None:
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
        lcs_status = self.data[mtdome.LlcName.LCS.value]
        for index, status in enumerate(lcs_status["status"]["status"]):
            if index in louver_ids:
                if target_positions[louver_ids.index(index)] > 0:
                    assert mtdome.LlcMotionState.OPEN.name == status
                else:
                    assert mtdome.LlcMotionState.CLOSED.name == status
            else:
                assert mtdome.LlcMotionState.CLOSED.name == status
        for index, positionActual in enumerate(lcs_status["positionActual"]):
            if index in louver_ids:
                assert target_positions[louver_ids.index(index)] == positionActual
            else:
                assert 0 == positionActual
        for index, positionCommanded in enumerate(lcs_status["positionCommanded"]):
            if index in louver_ids:
                assert target_positions[louver_ids.index(index)] == positionCommanded
            else:
                assert 0 == positionCommanded

    async def test_setLouvers(self) -> None:
        # Open some of the louvers and verify that their status and positions
        # are as expected.
        louver_ids = [5, 6, 7, 8, 9, 10]
        target_positions = [100.0, 80.0, 70.0, 85.0, 25.0, 60.0]
        await self.prepare_louvers(louver_ids, target_positions)
        await self.verify_louvers(louver_ids, target_positions)

        # Now close them.
        louver_ids = [5, 6, 7, 8, 9, 10]
        target_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        await self.prepare_louvers(louver_ids, target_positions)
        await self.verify_louvers(louver_ids, target_positions)

    async def test_closeLouvers(self) -> None:
        await self.write(command="closeLouvers", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to close.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[mtdome.LlcName.LCS.value]
        assert (
            lcs_status["status"]["status"]
            == [mtdome.LlcMotionState.CLOSED.name] * mtdome.mock_llc.NUM_LOUVERS
        )
        assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS
        assert lcs_status["positionCommanded"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS

    async def test_stopLouvers(self) -> None:
        louver_id = 5
        target_position = 100
        position = np.full(mtdome.mock_llc.NUM_LOUVERS, -1.0, dtype=float)
        position[louver_id] = target_position
        await self.write(
            command="setLouvers",
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="stopLouvers", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Give some time to the mock device to stop.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[mtdome.LlcName.LCS.value]
        assert (
            lcs_status["status"]["status"]
            == [mtdome.LlcMotionState.STOPPED.name] * mtdome.mock_llc.NUM_LOUVERS
        )
        assert lcs_status["positionActual"] == [0.0] * louver_id + [target_position] + [
            0.0
        ] * (mtdome.mock_llc.NUM_LOUVERS - louver_id - 1)
        assert lcs_status["positionCommanded"] == [0.0] * louver_id + [
            target_position
        ] + [0.0] * (mtdome.mock_llc.NUM_LOUVERS - louver_id - 1)

    async def test_openShutter(self) -> None:
        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        await self.validate_apscs(
            status=mtdome.LlcMotionState.OPEN,
            position_actual=[100.0, 100.0],
            position_commanded=100.0,
        )

    async def validate_apscs(
        self,
        status: mtdome.LlcMotionState = None,
        position_actual: list[float] = None,
        position_commanded: float = None,
    ) -> None:
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[mtdome.LlcName.APSCS.value]
        if status is not None:
            assert apscs_status["status"]["status"] == status.name
        if position_actual is not None:
            assert apscs_status["positionActual"] == position_actual
        if position_commanded is not None:
            assert apscs_status["positionCommanded"] == position_commanded

    async def test_closeShutter(self) -> None:
        await self.write(command="closeShutter", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        await self.validate_apscs(
            status=mtdome.LlcMotionState.CLOSED,
            position_actual=[0.0, 0.0],
            position_commanded=0.0,
        )

    async def test_stopShutter(self) -> None:
        await self.write(command="openShutter", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.apscs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="stopShutter", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        await self.validate_apscs(
            status=mtdome.LlcMotionState.STOPPED,
            position_actual=[100.0, 100.0],
            position_commanded=100.0,
        )

    async def validate_operational_mode(
        self, llc: mtdome.mock_llc.BaseMockStatus, command_part: str
    ) -> None:
        # Any lower level component should be in normal mode when started.
        assert llc.operational_mode == OperationalMode.NORMAL

        # Set the lower level component to DEGRADED and then send a command to
        # set it to normal again.
        llc.operational_mode = OperationalMode.DEGRADED
        await self.write(command=f"setNormal{command_part}", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert llc.operational_mode == OperationalMode.NORMAL

        # Send a command to set the lower level component to normal while
        # already in normal. This should not raise an exception.
        await self.write(command=f"setNormal{command_part}", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert llc.operational_mode == OperationalMode.NORMAL

        # Send a command to set the lower level component to degraded.
        await self.write(command=f"setDegraded{command_part}", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert llc.operational_mode == OperationalMode.DEGRADED

        # Send a command to set the lower level component to degraded while
        # already in degraded. This should not raise an exception.
        await self.write(command=f"setDegraded{command_part}", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert llc.operational_mode == OperationalMode.DEGRADED

        # Send a command to set the lower level component to normal again.
        await self.write(command=f"setNormal{command_part}", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert llc.operational_mode == OperationalMode.NORMAL

    async def test_operational_mode(self) -> None:
        await self.validate_operational_mode(self.mock_ctrl.amcs, "Az")
        await self.validate_operational_mode(self.mock_ctrl.apscs, "Shutter")
        await self.validate_operational_mode(self.mock_ctrl.lcs, "Louvers")
        await self.validate_operational_mode(self.mock_ctrl.lwscs, "El")
        await self.validate_operational_mode(self.mock_ctrl.moncs, "Monitoring")
        await self.validate_operational_mode(self.mock_ctrl.thcs, "Thermal")

    async def test_config(self) -> None:
        # All AMCS values within the limits.
        amcs_jmax = math.radians(2.0)
        amcs_amax = math.radians(0.5)
        amcs_vmax = math.radians(0.375)

        parameters = {
            "system": mtdome.LlcName.AMCS.value,
            "settings": [
                {"target": "jmax", "setting": [amcs_jmax]},
                {"target": "amax", "setting": [amcs_amax]},
                {"target": "vmax", "setting": [amcs_vmax]},
            ],
        }
        await self.write(command="config", parameters=parameters)
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        assert self.mock_ctrl.amcs.amcs_limits.jmax == amcs_jmax
        assert self.mock_ctrl.amcs.amcs_limits.amax == amcs_amax
        assert self.mock_ctrl.amcs.amcs_limits.vmax == amcs_vmax

        # All LWSCS values within the limits.
        lwscs_jmax = math.radians(2.5)
        lwscs_amax = math.radians(0.75)
        lwscs_vmax = math.radians(0.5)

        parameters = {
            "system": mtdome.LlcName.LWSCS.value,
            "settings": [
                {"target": "jmax", "setting": [lwscs_jmax]},
                {"target": "amax", "setting": [lwscs_amax]},
                {"target": "vmax", "setting": [lwscs_vmax]},
            ],
        }
        await self.write(command="config", parameters=parameters)
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        assert self.mock_ctrl.lwscs.lwscs_limits.jmax == lwscs_jmax
        assert self.mock_ctrl.lwscs.lwscs_limits.amax == lwscs_amax
        assert self.mock_ctrl.lwscs.lwscs_limits.vmax == lwscs_vmax

    async def test_park(self) -> None:
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
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.amcs.end_tai - _CURRENT_TAI
        )

        # Give some time to the mock device to move.
        wait_time = 0.2
        self.mock_ctrl.current_tai = (
            self.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + wait_time
        )

        await self.write(command="park", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.amcs.end_tai
            - _CURRENT_TAI
            - START_MOTORS_ADD_DURATION
            - wait_time
        )

        # Give some time to the mock device to park.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 5.0

        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == mtdome.LlcMotionState.PARKED.name
        assert amcs_status["positionActual"] == mtdome.mock_llc.PARK_POSITION
        assert amcs_status["positionCommanded"] == mtdome.mock_llc.PARK_POSITION

    async def test_setTemperature(self) -> None:
        temperature = 10.0
        await self.write(
            command="setTemperature", parameters={"temperature": temperature}
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to set the temperature.
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

        await self.write(command="statusThCS", parameters={})
        self.data = await self.read()
        thcs_status = self.data[mtdome.LlcName.THCS.value]
        assert thcs_status["status"]["status"] == mtdome.LlcMotionState.OPEN.name
        assert (
            thcs_status["temperature"]
            == [temperature] * mtdome.mock_llc.thcs.NUM_THERMO_SENSORS
        )

    async def test_inflate(self) -> None:
        # Make sure that the inflate status is set to OFF
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["inflate"] == mtdome.OnOff.OFF.value

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
        await self.write(
            command="inflate", parameters={"action": mtdome.OnOff.ON.value}
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION
        assert self.mock_ctrl.amcs.seal_inflated == mtdome.OnOff.ON
        # Also check that the inflate status is set in the AMCS status.
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["inflate"] == mtdome.OnOff.ON.value

    async def test_fans(self) -> None:
        # Make sure that the fans status is set to OFF
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["fans"] == mtdome.OnOff.OFF.value

        # Set the TAI time in the mock controller for easier control
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control
        self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
        await self.write(command="fans", parameters={"action": mtdome.OnOff.ON.value})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION
        assert self.mock_ctrl.amcs.fans_enabled == mtdome.OnOff.ON
        # Also check that the fans status is set in the AMCS status.
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["fans"] == mtdome.OnOff.ON.value

    async def test_status(self) -> None:
        await self.write(command="statusAMCS", parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == mtdome.LlcMotionState.PARKED.name
        assert amcs_status["positionActual"] == 0

        await self.write(command="statusApSCS", parameters={})
        self.data = await self.read()
        apscs_status = self.data[mtdome.LlcName.APSCS.value]
        assert apscs_status["status"]["status"] == mtdome.LlcMotionState.CLOSED.name
        assert apscs_status["positionActual"] == [0.0, 0.0]

        await self.write(command="statusLCS", parameters={})
        self.data = await self.read()
        lcs_status = self.data[mtdome.LlcName.LCS.value]
        assert (
            lcs_status["status"]["status"]
            == [mtdome.LlcMotionState.CLOSED.name] * mtdome.mock_llc.NUM_LOUVERS
        )
        assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS

        await self.write(command="statusLWSCS", parameters={})
        self.data = await self.read()
        lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
        assert lwscs_status["status"]["status"] == mtdome.LlcMotionState.STOPPED.name
        assert lwscs_status["positionActual"] == 0

        await self.write(command="statusMonCS", parameters={})
        self.data = await self.read()
        moncs_status = self.data[mtdome.LlcName.MONCS.value]
        assert moncs_status["status"]["status"] == mtdome.LlcMotionState.CLOSED.name
        assert moncs_status["data"] == [0.0] * mtdome.mock_llc.NUM_MON_SENSORS

        await self.write(command="statusThCS", parameters={})
        self.data = await self.read()
        thcs_status = self.data[mtdome.LlcName.THCS.value]
        assert thcs_status["status"]["status"] == mtdome.LlcMotionState.CLOSED.name
        assert thcs_status["temperature"] == [0.0] * mtdome.mock_llc.NUM_THERMO_SENSORS

    async def test_slow_network(self) -> None:
        """Test the slow network feature of the mock controller."""
        self.mock_ctrl.enable_slow_network = True
        await self.write(command="statusAMCS", parameters={})
        with pytest.raises(asyncio.exceptions.TimeoutError):
            # The default timeout should time out because of the slow network.
            await self.read()
        # Waiting longer should eventually result in a successful read.
        self.data = await self.read(timeout=SLOW_NETWORK_TIMEOUT)
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == mtdome.LlcMotionState.PARKED.name
        assert amcs_status["positionActual"] == 0

    async def test_network_interruption(self) -> None:
        """Test the network interruption feature of the mock controller."""
        self.mock_ctrl.enable_network_interruption = True
        await self.write(command="statusAMCS", parameters={})
        with pytest.raises(asyncio.exceptions.TimeoutError):
            # The default timeout should time out because of the network
            # interruption.
            await self.read()
        with pytest.raises(asyncio.exceptions.TimeoutError):
            # Waiting longer should also not result in a successful read.
            await self.read(timeout=SLOW_NETWORK_TIMEOUT)

    async def test_az_reset_drives(self) -> None:
        assert self.mock_ctrl.amcs.azimuth_motion.motion_state_in_error is False

        drives_in_error = [1, 1, 0, 0, 0]
        expected_drive_error_state = [True, True, False, False, False]
        await self.mock_ctrl.amcs.set_fault(0.0, drives_in_error=drives_in_error)
        assert (
            self.mock_ctrl.amcs.azimuth_motion.drives_in_error_state
            == expected_drive_error_state
        )
        assert self.mock_ctrl.amcs.azimuth_motion.motion_state_in_error is True

        expected_drive_error_state = [False, True, False, False, False]
        reset = [1, 0, 0, 0, 0]
        await self.mock_ctrl.reset_drives_az(reset=reset)
        assert (
            self.mock_ctrl.amcs.azimuth_motion.drives_in_error_state
            == expected_drive_error_state
        )
        assert self.mock_ctrl.amcs.azimuth_motion.motion_state_in_error is True

        expected_drive_error_state = [False, False, False, False, False]
        reset = [1, 1, 0, 0, 0]
        await self.mock_ctrl.reset_drives_az(reset=reset)
        assert (
            self.mock_ctrl.amcs.azimuth_motion.drives_in_error_state
            == expected_drive_error_state
        )
        assert self.mock_ctrl.amcs.azimuth_motion.motion_state_in_error is True

    async def test_shutter_reset_drives(self) -> None:
        assert self.mock_ctrl.apscs.motion_state_in_error is False

        drives_in_error = [1, 1, 0, 0]
        expected_drive_error_state = [True, True, False, False]
        await self.mock_ctrl.apscs.set_fault(drives_in_error=drives_in_error)
        assert self.mock_ctrl.apscs.drives_in_error_state == expected_drive_error_state
        assert self.mock_ctrl.apscs.motion_state_in_error is True

        expected_drive_error_state = [False, True, False, False]
        reset = [1, 0, 0, 0]
        await self.mock_ctrl.reset_drives_shutter(reset=reset)
        assert self.mock_ctrl.apscs.drives_in_error_state == expected_drive_error_state
        assert self.mock_ctrl.apscs.motion_state_in_error is True

        expected_drive_error_state = [False, False, False, False]
        reset = [1, 1, 0, 0]
        await self.mock_ctrl.reset_drives_shutter(reset=reset)
        assert self.mock_ctrl.apscs.drives_in_error_state == expected_drive_error_state
        assert self.mock_ctrl.apscs.motion_state_in_error is True

    async def test_az_exit_fault_and_reset_drives(self) -> None:
        """Test recovering AZ from an ERROR state."""
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
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(1.5),
        )
        await self.verify_amcs_move(
            0.5, mtdome.LlcMotionState.MOVING, math.radians(2.25)
        )

        # This sets the status of the AZ state machine to ERROR.
        drives_in_error = [1, 1, 0, 0, 0]
        expected_drive_error_state = [True, True, False, False, False]
        current_tai = self.mock_ctrl.current_tai + 0.1
        await self.mock_ctrl.amcs.set_fault(current_tai, drives_in_error)
        assert (
            self.mock_ctrl.amcs.azimuth_motion.drives_in_error_state
            == expected_drive_error_state
        )
        assert self.mock_ctrl.amcs.azimuth_motion.motion_state_in_error is True
        await self.verify_amcs_move(
            0.5, mtdome.LlcMotionState.ERROR, math.radians(2.40)
        )

        # Now call exit_fault. This will fail because there still are drives at
        # fault.
        await self.write(command="exitFault", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.COMMAND_REJECTED
        assert self.data["timeout"] == -1

        expected_drive_error_state = [False, False, False, False, False]
        reset = [1, 1, 0, 0, 0]
        await self.mock_ctrl.reset_drives_az(reset=reset)
        assert (
            self.mock_ctrl.amcs.azimuth_motion.drives_in_error_state
            == expected_drive_error_state
        )

        # Now call exit_fault which will not fail because the drives have been
        # reset.
        await self.mock_ctrl.exit_fault()
        await self.verify_amcs_move(
            0.0, mtdome.LlcMotionState.STATIONARY, math.radians(2.40)
        )

    async def test_shutter_exit_fault_and_reset_drives(self) -> None:
        """Test recovering the Aperture Shutter from an ERROR state."""
        # This sets the status of the state machine to ERROR.
        drives_in_error = [1, 1, 0, 0]
        expected_drive_error_state = [True, True, False, False]
        await self.mock_ctrl.apscs.set_fault(drives_in_error)
        assert self.mock_ctrl.apscs.drives_in_error_state == expected_drive_error_state
        assert self.mock_ctrl.apscs.motion_state_in_error is True
        await self.validate_apscs(status=mtdome.LlcMotionState.ERROR)

        # Now call exit_fault. This will fail because there still are drives at
        # fault.
        await self.write(command="exitFault", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.COMMAND_REJECTED
        assert self.data["timeout"] == -1

        expected_drive_error_state = [False, False, False, False]
        reset = [1, 1, 0, 0]
        await self.mock_ctrl.reset_drives_shutter(reset=reset)
        assert self.mock_ctrl.apscs.drives_in_error_state == expected_drive_error_state

        # Now call exit_fault which will not fail because the drives have been
        # reset.
        await self.mock_ctrl.exit_fault()
        await self.validate_apscs(status=mtdome.LlcMotionState.STATIONARY)

    async def test_calibrate_az(self) -> None:
        start_position = 0
        target_position = math.radians(10)
        target_velocity = math.radians(0.0)
        await self.prepare_amcs_move(
            start_position,
            target_position,
            target_velocity,
        )

        # Make the amcs rotate and check both status and position at the
        # specified times
        await self.verify_amcs_move(
            START_MOTORS_ADD_DURATION + 1.0,
            mtdome.LlcMotionState.MOVING,
            math.radians(1.5),
        )

        # Cannot calibrate while AMCS is MOVING
        await self.write(command="calibrateAz", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.COMMAND_REJECTED
        assert self.data["timeout"] == -1

        await self.verify_amcs_move(
            6.0,
            mtdome.LlcMotionState.STOPPED,
            math.radians(10.0),
        )

        # Can calibrate while AMCS is STOPPED
        await self.write(command="calibrateAz", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == 0.0

        await self.verify_amcs_move(
            7.0,
            mtdome.LlcMotionState.STOPPED,
            math.radians(0.0),
        )

    async def test_search_zero_shutter(self) -> None:
        initial_position_actual = np.full(
            mtdome.mock_llc.NUM_SHUTTERS, 5.0, dtype=float
        )
        self.mock_ctrl.apscs.position_actual = initial_position_actual
        await self.validate_apscs(
            position_actual=initial_position_actual.tolist(),
        )

        await self.write(command="searchZeroShutter", parameters={})
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION
        await self.validate_apscs(
            position_actual=np.zeros(
                mtdome.mock_llc.NUM_SHUTTERS, dtype=float
            ).tolist(),
        )

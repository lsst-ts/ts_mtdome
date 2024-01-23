# This file is part of ts_mtdome.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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

import contextlib
import logging
import math
import typing
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from lsst.ts import mtdome, tcpip, utils
from lsst.ts.mtdome.mock_llc.apscs import NUM_SHUTTERS
from lsst.ts.xml.enums.MTDome import MotionState, OnOff, OperationalMode

_CURRENT_TAI = 100001
START_MOTORS_ADD_DURATION = 5.5

# Default timeout for reads
DEFAULT_TIMEOUT = 1.0
# Long timeout in case of a mock network issue
SLOW_NETWORK_TIMEOUT = mtdome.MockMTDomeController.SLOW_NETWORK_SLEEP + 1.0

INDEX_ITER = utils.index_generator()


class MockControllerTestCase(tcpip.BaseOneClientServerTestCase):
    server_class = mtdome.MockMTDomeController

    async def asyncSetUp(self) -> None:
        # This is set to `any` to allow for invalid command_id data types. The
        # valid data type is int.
        self.command_id: typing.Any = -1
        self.data: dict | None = None
        self.log = logging.getLogger("MockTestCase")

    async def determine_current_tai(self) -> None:
        # Empty for mocking purposes.
        pass

    @contextlib.asynccontextmanager
    async def create_mtdome_controller(
        self, include_command_id: bool = True
    ) -> typing.AsyncGenerator[None, None]:
        async with self.create_server(
            connect_callback=self.connect_callback,
            include_command_id=include_command_id,
        ) as self.mock_ctrl:
            # Replace the determine_current_tai method with a mock method so
            # that the start_tai value on the mock_ctrl object can be set to
            # make sure that the mock_ctrl object behaves as if that amount of
            # time has passed.
            self.mock_ctrl.determine_current_tai = self.determine_current_tai
            yield

    @contextlib.asynccontextmanager
    async def create_client(self) -> typing.AsyncGenerator[None, None]:
        async with tcpip.Client(
            name="TestClient",
            host=self.mock_ctrl.host,
            port=self.mock_ctrl.port,
            log=self.log,
        ) as self.client:
            yield

    async def read(
        self, timeout: float = DEFAULT_TIMEOUT, assert_command_id: bool = True
    ) -> dict:
        """Utility function to read data using a ``tcpip.Client``.

        Parameters
        ----------
        timeout : `float`, optional
            The timeout to use; default to 1 [s].
        assert_command_id : `bool`, optional
            Assert the commandId in the read data or not; default True.

        Returns
        -------
        data : `dict`
            A dictionary with objects representing the string read.
        """
        data = await self.client.read_json()
        if assert_command_id:
            assert data["commandId"] == self.command_id
        return data

    async def write(
        self, command_id_to_use: typing.Any = None, **data: typing.Any
    ) -> None:
        """Utility function to write data using a ``tcpip.Client``.

        Parameters
        ----------
        command_id_to_use : `any`
            The command_id to use instead of generating one.
        data : `any`
            The data to go write.
        """
        if command_id_to_use:
            self.command_id = command_id_to_use
        else:
            self.command_id = next(INDEX_ITER)
        await self.client.write_json(data={"commandId": self.command_id, **data})

    async def test_too_many_command_parameters(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            await self.write(
                command=mtdome.CommandName.MOVE_AZ,
                parameters={"position": 0.1, "velocity": 0.1, "acceleration": 0.1},
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.INCORRECT_PARAMETERS
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
        self.mock_ctrl.amcs.azimuth_motion._end_position = start_position
        await self.write(
            command=mtdome.CommandName.MOVE_AZ,
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
        expected_status: MotionState,
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
        expected_status: `MotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        crawl_velocity: `float`
            The expected velocity if the expected status is CRAWLING in rad/s.
        """
        # Give some time to the mock device to move.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
        self.data = await self.read()
        amcs_status = self.data[mtdome.LlcName.AMCS.value]
        assert amcs_status["status"]["status"] == expected_status.name
        assert amcs_status["positionActual"] == pytest.approx(
            expected_position, rel=1e-3
        )

    async def test_moveAz_zero_pos_pos(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(1.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(3.0))
            await self.verify_amcs_move(
                5.0,
                MotionState.CRAWLING,
                math.radians(10.03),
                crawl_velocity=target_velocity,
            )

    async def test_moveAz_zero_pos_pos_in_two_steps(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Test moving the AMCS to a position in positive direction starting
            # from position 0 and ending in velocity == 0.0
            start_position = 0
            target_position_1 = math.radians(5.0)
            target_position_2 = math.radians(10.0)
            target_velocity = 0.0
            await self.prepare_amcs_move(
                start_position,
                target_position_1,
                target_velocity,
            )

            # Make the amcs rotate to the first target position and check both
            # status and position at the specified times
            await self.verify_amcs_move(
                START_MOTORS_ADD_DURATION + 1.0,
                MotionState.MOVING,
                math.radians(1.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(3.0))
            await self.verify_amcs_move(
                2.0,
                MotionState.STOPPED,
                math.radians(5.0),
                crawl_velocity=target_velocity,
            )

            # Make the amcs rotate to the second target position and check both
            # status and position at the specified times again
            await self.write(
                command=mtdome.CommandName.MOVE_AZ,
                parameters={"position": target_position_2, "velocity": target_velocity},
            )
            self.data = await self.read()
            await self.verify_amcs_move(
                2.0,
                MotionState.MOVING,
                math.radians(8.0),
            )
            await self.verify_amcs_move(
                4.0,
                MotionState.STOPPED,
                math.radians(10.0),
            )

    async def test_moveAz_zero_pos_neg(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(1.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(3.0))
            await self.verify_amcs_move(
                5.0,
                MotionState.CRAWLING,
                math.radians(9.97),
                crawl_velocity=target_velocity,
            )

    async def test_moveAz_zero_pos_zero(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Test moving the AMCS to a position in positive direction starting
            # from position 0 and ending in a stand still, i.e. a 0 crawl
            # velocity.
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
                MotionState.MOVING,
                math.radians(1.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(3.0))
            await self.verify_amcs_move(
                5.0,
                MotionState.STOPPED,
                math.radians(10.0),
                crawl_velocity=target_velocity,
            )

    async def test_moveAz_twenty_neg_pos(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(18.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(17.0))
            await self.verify_amcs_move(
                5.0,
                MotionState.CRAWLING,
                math.radians(10.03),
                crawl_velocity=target_velocity,
            )

    async def test_moveAz_twenty_neg_neg(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(18.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(17.0))
            await self.verify_amcs_move(
                5.0,
                MotionState.CRAWLING,
                math.radians(9.97),
                crawl_velocity=target_velocity,
            )

    async def test_moveAz_zero_neg_zero(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(18.5),
            )
            await self.verify_amcs_move(1.0, MotionState.MOVING, math.radians(17.0))
            await self.verify_amcs_move(
                5.0,
                MotionState.STOPPED,
                math.radians(10.0),
                crawl_velocity=target_velocity,
            )

    async def test_moveAz_error(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Test moving the AMCS to a position in positive direction starting
            # from position 0 and ending in a stand still, i.e. a 0 crawl
            # velocity.
            start_position = math.radians(20)
            target_position = math.radians(10)
            target_velocity = 0
            await self.prepare_amcs_move(
                start_position,
                target_position,
                target_velocity,
            )

            # Introduce errors. This will be improved once error codes have
            # been specified in a future Dome Software meeting.
            expected_messages = [
                {"code": 100, "description": "Drive 1 temperature too high"},
                {"code": 100, "description": "Drive 2 temperature too high"},
            ]
            assert self.mock_ctrl is not None
            self.mock_ctrl.amcs.messages = expected_messages

            # Give some time to the mock device to move and theck the error
            # status.
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.1
            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["messages"] == expected_messages

    async def test_crawlAz(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Set the TAI time in the mock controller for easier control
            assert self.mock_ctrl is not None
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device status TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
            target_velocity = math.radians(0.1)
            await self.write(
                command=mtdome.CommandName.CRAWL_AZ,
                parameters={"velocity": target_velocity},
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == pytest.approx(
                self.mock_ctrl.amcs.end_tai - _CURRENT_TAI
            )

            # Give some time to the mock device to move.
            self.mock_ctrl.current_tai = (
                self.mock_ctrl.current_tai + START_MOTORS_ADD_DURATION + 1.0
            )

            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.CRAWLING.name
            assert amcs_status["positionActual"] >= math.radians(0.05)
            assert amcs_status["positionActual"] <= math.radians(0.15)

    async def test_stopAz(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(1.5),
            )

            await self.write(command=mtdome.CommandName.STOP_AZ, parameters={})
            # Give some time to the mock device to stop moving.
            assert self.mock_ctrl is not None
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == pytest.approx(0.0)

            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.STOPPED.name
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
        await self.write(
            command=mtdome.CommandName.MOVE_EL, parameters={"position": target_position}
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == pytest.approx(
            self.mock_ctrl.lwscs.end_tai - _CURRENT_TAI
        )

    async def verify_lwscs_motion(
        self,
        time_diff: float,
        expected_status: MotionState,
        expected_position: float,
    ) -> None:
        """Verify the expected status and position after the given time
        difference.

        Parameters
        ----------
        time_diff: `float`
            The time difference since the previous status check in seconds.
        expected_status: `MotionState`
            The expected status.
        expected_position: `float`
            The expected position in radians.
        """
        # Give some time to the mock device to move.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + time_diff
        await self.write(command=mtdome.CommandName.STATUS_LWSCS, parameters={})
        self.data = await self.read()
        lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
        assert lwscs_status["status"]["status"] == expected_status.name
        assert lwscs_status["positionActual"] == pytest.approx(expected_position, 3)

    async def test_moveEl_zero_five(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Test moving the LWSCS from 0 to 5 degrees. This should succeed.
            start_position = 0
            target_position = math.radians(5)
            await self.prepare_lwscs_move(
                start_position=start_position, target_position=target_position
            )

            # Move EL and check the position.
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.MOVING,
                expected_position=math.radians(1.75),
            )
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.MOVING,
                expected_position=math.radians(3.5),
            )
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.STOPPED,
                expected_position=math.radians(5.0),
            )

    async def test_moveEl_five_zero(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Test moving the LWSCS from 5 to 0 degrees. This should succeed.
            start_position = math.radians(5)
            target_position = math.radians(0)
            await self.prepare_lwscs_move(
                start_position=start_position, target_position=target_position
            )

            # Move EL and check the position.
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.MOVING,
                expected_position=math.radians(3.25),
            )
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.MOVING,
                expected_position=math.radians(1.5),
            )
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.STOPPED,
                expected_position=math.radians(0),
            )

    async def test_moveEl_five_min_five(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Test moving the LWSCS from 5 to -5 degrees. This should NOT
            # succeed.
            start_position = math.radians(5)
            target_position = math.radians(-5)
            # Sending the command should result in a ValueError. The exception
            # encountered here is a TimeoutError, which is why a much more
            # general Exception is caught.
            try:
                await self.prepare_lwscs_move(
                    start_position=start_position, target_position=target_position
                )
                self.fail("A ValueError should have been raised.")
            except Exception:
                pass

    async def test_stopEl(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            start_position = 0
            target_position = math.radians(5)
            await self.prepare_lwscs_move(
                start_position=start_position, target_position=target_position
            )

            # Move EL and check the position and status.
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.MOVING,
                expected_position=math.radians(1.75),
            )

            await self.write(command=mtdome.CommandName.STOP_EL, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == pytest.approx(0.0)

            await self.write(command=mtdome.CommandName.STATUS_LWSCS, parameters={})
            self.data = await self.read()
            lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
            assert lwscs_status["status"]["status"] == MotionState.STOPPED.name
            assert lwscs_status["positionActual"] >= math.radians(1.7)
            assert lwscs_status["positionActual"] <= math.radians(1.9)

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
        # Set the TAI time in the mock controller for easier control.
        assert self.mock_ctrl is not None
        self.mock_ctrl.current_tai = _CURRENT_TAI
        self.mock_ctrl.lwscs.elevation_motion._start_position = start_position
        await self.write(
            command=mtdome.CommandName.CRAWL_EL,
            parameters={"velocity": target_velocity},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.data["timeout"] == self.mock_ctrl.lwscs.end_tai - _CURRENT_TAI

    async def test_crawlEl(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            await self.prepare_lwscs_crawl(
                start_position=0, target_velocity=math.radians(0.1)
            )

            # Let EL crawl a little and check the position.
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.CRAWLING,
                expected_position=math.radians(0.1),
            )
            await self.verify_lwscs_motion(
                time_diff=1.0,
                expected_status=MotionState.CRAWLING,
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
        self.mock_ctrl.lcs.current_state[:] = MotionState.STOPPED.name
        self.mock_ctrl.lcs.target_state[:] = MotionState.STOPPED.name
        position = np.full(mtdome.mock_llc.NUM_LOUVERS, -1.0, dtype=float)
        for index, louver_id in enumerate(louver_ids):
            position[louver_id] = target_positions[index]
        await self.write(
            command=mtdome.CommandName.SET_LOUVERS,
            parameters={"position": position.tolist()},
        )
        self.data = await self.read()
        assert self.data["response"] == mtdome.ResponseCode.OK
        assert self.mock_ctrl is not None
        assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

        # Set the TAI time in the mock controller for easier control.
        self.mock_ctrl.current_tai = _CURRENT_TAI
        # Set the mock device statuses TAI time to the mock controller time for
        # easier control.
        self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
        # Give some time to the mock device to open.
        await self.mock_ctrl.lcs.evaluate_state(self.mock_ctrl.current_tai)
        self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 31.0
        await self.mock_ctrl.lcs.evaluate_state(self.mock_ctrl.current_tai)

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
        await self.write(command=mtdome.CommandName.STATUS_LCS, parameters={})
        self.data = await self.read()

        # See mock_llc.lcs for what the structure of lcs looks like as well as
        # for the meaning of LlcStatus.
        lcs_status = self.data[mtdome.LlcName.LCS.value]
        for index, status in enumerate(lcs_status["status"]["status"]):
            if index in louver_ids:
                if target_positions[louver_ids.index(index)] > 0:
                    if self.mock_ctrl.current_tai == _CURRENT_TAI:
                        assert MotionState.MOVING.name == status
                else:
                    assert MotionState.STOPPED.name == status
            else:
                assert MotionState.STOPPED.name == status
        for index, position_actual in enumerate(lcs_status["positionActual"]):
            if index in louver_ids:
                assert target_positions[louver_ids.index(index)] == position_actual
            else:
                assert 0 == position_actual
        for index, position_commanded in enumerate(lcs_status["positionCommanded"]):
            if index in louver_ids:
                assert target_positions[louver_ids.index(index)] == position_commanded
            else:
                assert 0 == position_commanded

    async def test_setLouvers(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Open some of the louvers and verify that their status and
            # positions are as expected.
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
        async with self.create_mtdome_controller(), self.create_client():
            await self.write(command=mtdome.CommandName.CLOSE_LOUVERS, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device statuses TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
            # Give some time to the mock device to close.
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

            await self.write(command=mtdome.CommandName.STATUS_LCS, parameters={})
            self.data = await self.read()
            lcs_status = self.data[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [MotionState.ENABLING_MOTOR_POWER.name] * mtdome.mock_llc.NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS
            assert (
                lcs_status["positionCommanded"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS
            )

    async def test_stopLouvers(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            self.mock_ctrl.lcs.current_state[:] = MotionState.STOPPED.name
            self.mock_ctrl.lcs.target_state[:] = MotionState.STOPPED.name
            louver_id = 5
            target_position = 100
            position = np.full(mtdome.mock_llc.NUM_LOUVERS, -1.0, dtype=float)
            position[louver_id] = target_position
            await self.write(
                command=mtdome.CommandName.SET_LOUVERS,
                parameters={"position": position.tolist()},
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device statuses TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.lcs.command_time_tai = self.mock_ctrl.current_tai
            # Give some time to the mock device to open.
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

            await self.write(command=mtdome.CommandName.STOP_LOUVERS, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

            # Give some time to the mock device to stop.
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

            await self.write(command=mtdome.CommandName.STATUS_LCS, parameters={})
            self.data = await self.read()
            lcs_status = self.data[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [MotionState.STOPPED.name] * mtdome.mock_llc.NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS
            assert lcs_status["positionCommanded"] == [0.0] * louver_id + [
                target_position
            ] + [0.0] * (mtdome.mock_llc.NUM_LOUVERS - louver_id - 1)

    async def test_openShutter(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI

            await self.write(command=mtdome.CommandName.OPEN_SHUTTER, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            # It takes 10 seconds to open the shutters.
            assert self.data["timeout"] == pytest.approx(10.0)

            await self.validate_apscs(
                status=MotionState.MOVING,
                position_actual=[0.0, 0.0],
                position_commanded=[100.0, 100.0],
            )
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 5.0
            await self.validate_apscs(
                status=MotionState.MOVING,
                position_actual=[50.0, 50.0],
                position_commanded=[100.0, 100.0],
            )
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 10.0
            await self.validate_apscs(
                status=MotionState.STOPPED,
                position_actual=[100.0, 100.0],
                position_commanded=[100.0, 100.0],
            )

    async def validate_apscs(
        self,
        status: MotionState = None,
        position_actual: list[float] | None = None,
        position_commanded: list[float] | None = None,
    ) -> None:
        await self.write(command=mtdome.CommandName.STATUS_APSCS, parameters={})
        self.data = await self.read()
        apscs_status = self.data[mtdome.LlcName.APSCS.value]
        if status is not None:
            assert apscs_status["status"]["status"] == [status.name, status.name]
        if position_actual is not None:
            assert apscs_status["positionActual"] == pytest.approx(position_actual)
        if position_commanded is not None:
            assert apscs_status["positionCommanded"] == pytest.approx(
                position_commanded
            )

    async def test_closeShutter(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI

            await self.write(command=mtdome.CommandName.CLOSE_SHUTTER, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            assert self.data["timeout"] == pytest.approx(0.0)

            await self.validate_apscs(
                status=MotionState.STOPPED,
                position_actual=[0.0, 0.0],
                position_commanded=[0.0, 0.0],
            )

    async def test_stopShutter(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI

            await self.write(command=mtdome.CommandName.OPEN_SHUTTER, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            expected_duration = 10.0  # The shutters move from closed to open.
            assert self.data["timeout"] == pytest.approx(expected_duration)

            # Give some time to the mock device to open.
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

            await self.write(command=mtdome.CommandName.STOP_SHUTTER, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == pytest.approx(
                0.0
            )  # stopping is instantaneous.

            await self.validate_apscs(
                status=MotionState.STOPPED,
                position_actual=[2.0, 2.0],
                position_commanded=[100.0, 100.0],
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
        async with self.create_mtdome_controller(), self.create_client():
            await self.validate_operational_mode(self.mock_ctrl.amcs, "Az")
            await self.validate_operational_mode(self.mock_ctrl.apscs, "Shutter")
            await self.validate_operational_mode(self.mock_ctrl.lcs, "Louvers")
            await self.validate_operational_mode(self.mock_ctrl.lwscs, "El")
            await self.validate_operational_mode(self.mock_ctrl.moncs, "Monitoring")
            await self.validate_operational_mode(self.mock_ctrl.thcs, "Thermal")

    async def test_config(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
            await self.write(command=mtdome.CommandName.CONFIG, parameters=parameters)
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

            assert self.mock_ctrl.amcs.jmax == amcs_jmax
            assert self.mock_ctrl.amcs.amax == amcs_amax
            assert self.mock_ctrl.amcs.vmax == amcs_vmax

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
            await self.write(command=mtdome.CommandName.CONFIG, parameters=parameters)
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

            assert self.mock_ctrl.lwscs.jmax == lwscs_jmax
            assert self.mock_ctrl.lwscs.amax == lwscs_amax
            assert self.mock_ctrl.lwscs.vmax == lwscs_vmax

    async def test_park(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device statuses TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.amcs.command_time_tai = self.mock_ctrl.current_tai
            target_position = math.radians(1)
            target_velocity = math.radians(0.1)
            await self.write(
                command=mtdome.CommandName.MOVE_AZ,
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

            await self.write(command=mtdome.CommandName.PARK, parameters={})
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

            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["positionActual"] == mtdome.mock_llc.PARK_POSITION
            assert amcs_status["positionCommanded"] == mtdome.mock_llc.PARK_POSITION

    async def test_setTemperature(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            temperature = 10.0
            await self.write(
                command=mtdome.CommandName.SET_TEMPERATURE,
                parameters={"temperature": temperature},
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION

            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device statuses TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
            # Give some time to the mock device to set the temperature.
            self.mock_ctrl.current_tai = self.mock_ctrl.current_tai + 0.2

            await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
            self.data = await self.read()
            thcs_status = self.data[mtdome.LlcName.THCS.value]
            assert thcs_status["status"]["status"] == MotionState.DISABLED.name
            assert (
                thcs_status["temperature"]
                == [temperature] * mtdome.mock_llc.thcs.NUM_THERMO_SENSORS
            )

    async def test_inflate(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Make sure that the inflate status is set to OFF.
            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"][mtdome.CommandName.INFLATE] == OnOff.OFF.value

            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device statuses TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
            await self.write(
                command=mtdome.CommandName.INFLATE,
                parameters={"action": OnOff.ON.value},
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION
            assert self.mock_ctrl.amcs.seal_inflated == OnOff.ON
            # Also check that the inflate status is set in the AMCS status.
            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"][mtdome.CommandName.INFLATE] == OnOff.ON.value

    async def test_fans(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            # Make sure that the fans status is set to OFF
            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"][mtdome.CommandName.FANS] == pytest.approx(0.0)

            # Set the TAI time in the mock controller for easier control.
            self.mock_ctrl.current_tai = _CURRENT_TAI
            # Set the mock device statuses TAI time to the mock controller time
            # for easier control.
            self.mock_ctrl.thcs.command_time_tai = self.mock_ctrl.current_tai
            await self.write(
                command=mtdome.CommandName.FANS, parameters={"speed": 75.0}
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.mock_ctrl is not None
            assert self.data["timeout"] == mtdome.MockMTDomeController.LONG_DURATION
            assert self.mock_ctrl.amcs.fans_speed == pytest.approx(75.0)
            # Also check that the fans status is set in the AMCS status.
            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"][mtdome.CommandName.FANS] == pytest.approx(75.0)

    async def test_status(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
            self.data = await self.read()
            amcs_status = self.data[mtdome.LlcName.AMCS.value]
            assert amcs_status["status"]["status"] == MotionState.PARKED.name
            assert amcs_status["positionActual"] == 0

            await self.validate_apscs(
                status=MotionState.STOPPED, position_actual=[0.0, 0.0]
            )

            self.mock_ctrl.lcs.current_state[:] = MotionState.STOPPED.name
            self.mock_ctrl.lcs.target_state[:] = MotionState.STOPPED.name
            await self.write(command=mtdome.CommandName.STATUS_LCS, parameters={})
            self.data = await self.read()
            lcs_status = self.data[mtdome.LlcName.LCS.value]
            assert (
                lcs_status["status"]["status"]
                == [MotionState.STOPPED.name] * mtdome.mock_llc.NUM_LOUVERS
            )
            assert lcs_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_LOUVERS

            await self.write(command=mtdome.CommandName.STATUS_LWSCS, parameters={})
            self.data = await self.read()
            lwscs_status = self.data[mtdome.LlcName.LWSCS.value]
            assert lwscs_status["status"]["status"] == MotionState.STOPPED.name
            assert lwscs_status["positionActual"] == 0

            await self.write(command=mtdome.CommandName.STATUS_MONCS, parameters={})
            self.data = await self.read()
            moncs_status = self.data[mtdome.LlcName.MONCS.value]
            assert moncs_status["status"]["status"] == MotionState.CLOSED.name
            assert moncs_status["data"] == [0.0] * mtdome.mock_llc.NUM_MON_SENSORS

            await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
            self.data = await self.read()
            thcs_status = self.data[mtdome.LlcName.THCS.value]
            assert thcs_status["status"]["status"] == MotionState.DISABLED.name
            assert (
                thcs_status["temperature"] == [0.0] * mtdome.mock_llc.NUM_THERMO_SENSORS
            )

            await self.write(command=mtdome.CommandName.STATUS_RAD, parameters={})
            self.data = await self.read()
            rad_status = self.data[mtdome.LlcName.RAD.value]
            assert (
                rad_status["status"]["status"]
                == [MotionState.CLOSED.name] * mtdome.mock_llc.NUM_DOORS
            )
            assert rad_status["positionActual"] == [0.0] * mtdome.mock_llc.NUM_DOORS

            await self.write(command=mtdome.CommandName.STATUS_CSCS, parameters={})
            self.data = await self.read()
            cscs_status = self.data[mtdome.LlcName.CSCS.value]
            assert cscs_status["status"]["status"] == MotionState.STOPPED.name
            assert cscs_status["positionActual"] == pytest.approx(0.0)

    async def test_az_reset_drives(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
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
        async with self.create_mtdome_controller(), self.create_client():
            for i in range(NUM_SHUTTERS):
                assert (
                    self.mock_ctrl.apscs.shutter_motion[i].motion_state_in_error
                    is False
                )

            drives_in_error = [0, 1, 0, 1]
            expected_drive_error_state = [False, True]
            await self.mock_ctrl.apscs.set_fault(_CURRENT_TAI, drives_in_error)
            for i in range(NUM_SHUTTERS):
                assert (
                    self.mock_ctrl.apscs.shutter_motion[i].drives_in_error_state
                    == expected_drive_error_state
                )
                assert (
                    self.mock_ctrl.apscs.shutter_motion[i].motion_state_in_error is True
                )

    async def test_az_exit_fault_and_reset_drives(self) -> None:
        """Test recovering AZ from an ERROR state."""
        async with self.create_mtdome_controller(), self.create_client():
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
                MotionState.MOVING,
                math.radians(1.5),
            )
            await self.verify_amcs_move(0.5, MotionState.MOVING, math.radians(2.25))

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
            await self.verify_amcs_move(0.5, MotionState.ERROR, math.radians(2.40))

            # Now call exit_fault. This will fail because there still are
            # drives at fault.
            await self.write(command=mtdome.CommandName.EXIT_FAULT, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.INCORRECT_PARAMETERS
            assert self.data["timeout"] == -1

            expected_drive_error_state = [False, False, False, False, False]
            reset = [1, 1, 0, 0, 0]
            await self.mock_ctrl.reset_drives_az(reset=reset)
            assert (
                self.mock_ctrl.amcs.azimuth_motion.drives_in_error_state
                == expected_drive_error_state
            )

            # Now call exit_fault which will not fail because the drives have
            # been reset.
            await self.mock_ctrl.exit_fault()
            await self.verify_amcs_move(
                0.0, mtdome.InternalMotionState.STATIONARY, math.radians(2.40)
            )

    async def test_shutter_exit_fault_and_reset_drives(self) -> None:
        """Test recovering the Aperture Shutter from an ERROR state."""
        async with self.create_mtdome_controller(), self.create_client():
            # This sets the status of the state machine to ERROR.
            drives_in_error = [0, 1, 0, 1]
            expected_drive_error_state = [False, True]
            await self.mock_ctrl.apscs.set_fault(_CURRENT_TAI, drives_in_error)
            for i in range(NUM_SHUTTERS):
                assert (
                    self.mock_ctrl.apscs.shutter_motion[i].drives_in_error_state
                    == expected_drive_error_state
                )
                assert (
                    self.mock_ctrl.apscs.shutter_motion[i].motion_state_in_error is True
                )
            await self.validate_apscs(status=MotionState.ERROR)

            # Now call exit_fault. This will fail because there still are
            # drives at fault.
            await self.write(command=mtdome.CommandName.EXIT_FAULT, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.INCORRECT_PARAMETERS
            assert self.data["timeout"] == -1

            expected_drive_error_state = [False, False]
            reset = [0, 1, 0, 1]
            await self.mock_ctrl.reset_drives_shutter(reset=reset)
            for i in range(NUM_SHUTTERS):
                assert (
                    self.mock_ctrl.apscs.shutter_motion[i].drives_in_error_state
                    == expected_drive_error_state
                )

            # Now call exit_fault which will not fail because the drives have
            # been reset.
            await self.mock_ctrl.exit_fault()
            await self.validate_apscs(status=mtdome.InternalMotionState.STATIONARY)

    async def test_calibrate_az(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            start_position = 0
            target_position = math.radians(10)
            target_velocity = math.radians(0.0)
            await self.prepare_amcs_move(
                start_position,
                target_position,
                target_velocity,
            )

            # Make the amcs rotate and check both status and position at the
            # specified times.
            await self.verify_amcs_move(
                START_MOTORS_ADD_DURATION + 1.0,
                MotionState.MOVING,
                math.radians(1.5),
            )

            # Cannot calibrate while AMCS is MOVING.
            await self.write(command=mtdome.CommandName.CALIBRATE_AZ, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.INCORRECT_PARAMETERS
            assert self.data["timeout"] == -1

            await self.verify_amcs_move(
                6.0,
                MotionState.STOPPED,
                math.radians(10.0),
            )

            # Can calibrate while AMCS is STOPPED.
            await self.write(command=mtdome.CommandName.CALIBRATE_AZ, parameters={})
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == pytest.approx(0.0)

            await self.verify_amcs_move(
                7.0,
                MotionState.STOPPED,
                math.radians(0.0),
            )

    async def test_search_zero_shutter(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            initial_position_actual = np.full(
                mtdome.mock_llc.NUM_SHUTTERS, 0.0, dtype=float
            )
            self.mock_ctrl.apscs.position_actual = initial_position_actual
            await self.validate_apscs(
                position_actual=initial_position_actual.tolist(),
            )

            await self.write(
                command=mtdome.CommandName.SEARCH_ZERO_SHUTTER, parameters={}
            )
            self.data = await self.read()
            assert self.data["response"] == mtdome.ResponseCode.OK
            assert self.data["timeout"] == pytest.approx(0.0)
            await self.validate_apscs(
                position_actual=np.zeros(
                    mtdome.mock_llc.NUM_SHUTTERS, dtype=float
                ).tolist(),
            )

    async def test_invalid_command_id(self) -> None:
        async with self.create_mtdome_controller(), self.create_client():
            await self.write(
                command_id_to_use="1.1",
                command=mtdome.CommandName.MOVE_AZ,
                parameters={"position": 0.1, "velocity": 0.1},
            )
            self.data = await self.read(assert_command_id=False)
            assert self.data["response"] == mtdome.ResponseCode.INCORRECT_PARAMETERS
            assert self.data["timeout"] == -1

    # TODO DM-39564: Remove this test as soon as the MTDome control software
    #   always includes a commandId in its data.
    async def test_no_command_id(self) -> None:
        async with self.create_mtdome_controller(
            include_command_id=False
        ), self.create_client():
            await self.write(
                command=mtdome.CommandName.MOVE_AZ,
                parameters={"position": 0.1, "velocity": 0.1},
            )
            self.data = await self.read(assert_command_id=False)
            assert self.data["response"] == mtdome.ResponseCode.INCORRECT_PARAMETERS
            assert self.data["timeout"] == -1

    async def test_start_stop_thermal_control(self) -> None:
        with patch(
            "lsst.ts.mtdome.mock_llc.mock_motion.AzimuthMotion.get_position_velocity_and_motion_state",
            MagicMock(),
        ) as mock:
            async with self.create_mtdome_controller(), self.create_client():
                await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
                self.data = await self.read()
                thcs_status = self.data[mtdome.LlcName.THCS.value]
                assert thcs_status["status"]["status"] == MotionState.DISABLED.name

                mock.return_value = (0.0, 0.0, MotionState.STARTING_MOTOR_COOLING)
                await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
                await self.read()
                await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
                self.data = await self.read()
                thcs_status = self.data[mtdome.LlcName.THCS.value]
                assert thcs_status["status"]["status"] == MotionState.ENABLING.name
                await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
                self.data = await self.read()
                thcs_status = self.data[mtdome.LlcName.THCS.value]
                assert thcs_status["status"]["status"] == MotionState.ENABLED.name

                mock.return_value = (0.0, 0.0, MotionState.STOPPING_MOTOR_COOLING)
                await self.write(command=mtdome.CommandName.STATUS_AMCS, parameters={})
                await self.read()
                await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
                self.data = await self.read()
                thcs_status = self.data[mtdome.LlcName.THCS.value]
                assert thcs_status["status"]["status"] == MotionState.DISABLING.name
                await self.write(command=mtdome.CommandName.STATUS_THCS, parameters={})
                self.data = await self.read()
                thcs_status = self.data[mtdome.LlcName.THCS.value]
                assert thcs_status["status"]["status"] == MotionState.DISABLED.name

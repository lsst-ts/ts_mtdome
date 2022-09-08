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

import logging
import math
import unittest

import pytest
from expected_state import ExpectedState
from lsst.ts import mtdome
from lsst.ts.mtdome.mock_llc.amcs import (
    POWER_PER_MOTOR_CRAWLING,
    POWER_PER_MOTOR_MOVING,
)
from lsst.ts.mtdome.mock_llc.mock_motion.azimuth_motion import NUM_MOTORS

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

# The maximum AZ rotation speed (deg/s)
MAX_SPEED = 4.0
START_TAI = 10001.0
# The amount of time needed before the motors of the AZ rotation begin moving.
START_MOTORS_ADD_DURATION = 5.5


class AmcsTestCase(unittest.IsolatedAsyncioTestCase):
    async def prepare_amcs(
        self, start_position: float, max_speed: float, start_tai: float
    ) -> None:
        """Prepare the AmcsStatus for future commands.

        Parameters
        ----------
        start_position: `float`
            The start position of the azimuth motion [deg].
        max_speed: `float`
            The maximum allowed speed [deg/s].
        start_tai: `float`
            The start TAI time.
        """
        self.amcs = mtdome.mock_llc.AmcsStatus(start_tai=start_tai)
        azimuth_motion = mtdome.mock_llc.AzimuthMotion(
            start_position=math.radians(start_position),
            max_speed=math.radians(max_speed),
            start_tai=start_tai,
        )
        self.amcs.azimuth_motion = azimuth_motion

    async def verify_amcs_state(
        self,
        tai: float,
        expected_position: float,
        expected_velocity: float,
        expected_motion_state: mtdome.LlcMotionState,
    ) -> None:
        """Verify the position of the AmcsStatus at the given TAI
        time.

        Parameters
        ----------
        tai: `float`
            The TAI time to compute the position for.
        expected_position: `float`
            The expected position at the given TAI time [deg].
        expected_velocity: `float`
            The expected velocity at the given TAI time [deg/s].
        expected_motion_state: `float`
            The expected motion state at the given TAI time.
        """
        await self.amcs.determine_status(current_tai=tai)
        assert math.degrees(self.amcs.llc_status["positionActual"]) == pytest.approx(
            expected_position
        )
        assert math.degrees(self.amcs.llc_status["velocityActual"]) == pytest.approx(
            expected_velocity
        )
        assert expected_motion_state.name == self.amcs.llc_status["status"]["status"]
        expected_drive_current: list[float] = [0.0] * NUM_MOTORS
        if expected_motion_state == mtdome.LlcMotionState.MOVING:
            expected_drive_current = [POWER_PER_MOTOR_MOVING] * NUM_MOTORS
        elif expected_motion_state == mtdome.LlcMotionState.CRAWLING:
            expected_drive_current = [POWER_PER_MOTOR_CRAWLING] * NUM_MOTORS
        assert expected_drive_current == self.amcs.llc_status["driveCurrentActual"]

    async def verify_move_duration(
        self,
        target_position: float,
        crawl_velocity: float,
        start_tai: float,
        expected_duration: float,
    ) -> None:
        duration = await self.amcs.moveAz(
            position=math.radians(target_position),
            velocity=math.radians(crawl_velocity),
            start_tai=start_tai,
        )
        assert pytest.approx(duration) == expected_duration

    async def verify_crawl_duration(
        self,
        crawl_velocity: float,
        start_tai: float,
        expected_duration: float,
    ) -> None:
        duration = await self.amcs.crawlAz(
            velocity=math.radians(crawl_velocity),
            start_tai=start_tai,
        )
        assert pytest.approx(duration) == expected_duration

    async def verify_halt(
        self,
        start_tai: float,
        expected_states: list[ExpectedState],
        command: str,
    ) -> None:
        func = getattr(self.amcs, command)
        await func(start_tai=START_TAI + START_MOTORS_ADD_DURATION + start_tai)
        for expected_state in expected_states:
            tai = expected_state.tai
            await self.verify_amcs_state(
                tai=START_TAI + START_MOTORS_ADD_DURATION + tai,
                expected_position=expected_state.position,
                expected_velocity=expected_state.velocity,
                expected_motion_state=expected_state.motion_state,
            )

    async def verify_amcs(
        self,
        command: str,
        start_position: float,
        target_position: float,
        max_speed: float,
        crawl_velocity: float,
        expected_duration: float,
        expected_states: list[ExpectedState],
        start_tai: float,
    ) -> None:
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        if command == "move":
            await self.verify_move_duration(
                target_position, crawl_velocity, start_tai, expected_duration
            )
        elif command == "crawl":
            await self.verify_crawl_duration(
                crawl_velocity, start_tai, expected_duration
            )
        else:
            self.fail(f"Unsupported {command!r} received.")
        for expected_state in expected_states:
            tai = expected_state.tai
            await self.verify_amcs_state(
                tai=START_TAI + START_MOTORS_ADD_DURATION + tai,
                expected_position=expected_state.position,
                expected_velocity=expected_state.velocity,
                expected_motion_state=expected_state.motion_state,
            )

    async def test_move_zero_ten_pos(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 degrees and then crawl in positive direction.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 8.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.5, 10.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(4.0, 10.15, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_zero_ten_neg(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 degrees and then crawl in negative direction.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = -0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 8.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.5, 10.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(4.0, 9.85, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_zero_pos(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 0 degrees and then crawl in positive direction.
        """
        start_position = 10.0
        start_tai = START_TAI
        target_position = 0.0
        crawl_velocity = 0.1
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 6.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.5, 0.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(4.0, 0.15, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_zero_neg(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 0 degrees and then crawl in negative direction.
        """
        start_position = 10.0
        start_tai = START_TAI
        target_position = 0.0
        crawl_velocity = -0.1
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 6.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.5, 0.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(4.0, 359.85, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_threefifty_pos(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in positive direction.
        """
        start_position = 10.0
        start_tai = START_TAI
        target_position = 350.0
        crawl_velocity = 0.1
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position - 360.0) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 6.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 358.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(5.0, 350.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(6.0, 350.1, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_threefifty_neg(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in negative direction.
        """
        start_position = 10.0
        start_tai = START_TAI
        target_position = 350.0
        crawl_velocity = -0.1
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position - 360.0) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 6.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 358.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(5.0, 350.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(6.0, 349.9, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_threefifty_ten_pos(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in positive direction.
        """
        start_position = 350.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = math.fabs(
            START_MOTORS_ADD_DURATION
            + (target_position - start_position + 360.0) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 354.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 358.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 2.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(5.0, 10.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(6.0, 10.1, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_threefifty_ten_neg(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in negative direction.
        """
        start_position = 350.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = -0.1
        expected_duration = math.fabs(
            START_MOTORS_ADD_DURATION
            + (target_position - start_position + 360.0) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 354.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(2.0, 358.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 2.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(5.0, 10.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(6.0, 9.9, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_crawl_pos(self) -> None:
        """Test the AmcsStatus when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        start_position = 350.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 351.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(2.0, 352.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(10.0, 0.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(11.0, 1.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(20.0, 10.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(21.0, 11.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="crawl",
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_crawl_neg(self) -> None:
        """Test the AmcsStatus when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = -1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 9.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(2.0, 8.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(10.0, 0.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(11.0, 359.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(20.0, 350.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
            ExpectedState(21.0, 349.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="crawl",
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_stop_from_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 and getting stopped while moving.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(3.0, 8.0, 0.0, mtdome.LlcMotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=2.0,
            expected_states=expected_states,
            command="stopAz",
        )

    async def test_stop_from_crawling_after_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10, start crawling and then getting stopped while crawling.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 10.05, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 10.15, 0.0, mtdome.LlcMotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="stopAz",
        )

    async def test_stop_from_crawling(self) -> None:
        """Test the AmcsStatus when crawling and then getting
        stopped.
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 11.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="crawl",
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 14.0, 0.0, mtdome.LlcMotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="stopAz",
        )

    async def test_park_from_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 and getting parked while moving.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(1.0, 4.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 0.0, 0.0, mtdome.LlcMotionState.PARKED),
        ]
        await self.verify_halt(
            start_tai=1.0,
            expected_states=expected_states,
            command="park",
        )

    async def test_park_from_crawling_after_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10, start crawling and then getting parked while crawling.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 10.05, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 6.15, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(6.0, 2.15, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(7.0, 0.0, 0.0, mtdome.LlcMotionState.PARKED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="park",
        )

    async def test_park_from_crawling(self) -> None:
        """Test the AmcsStatus when crawling and then getting
        parked.
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 11.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="crawl",
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 10.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(6.0, 6.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(7.0, 2.0, -MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(8.0, 0.0, 0.0, mtdome.LlcMotionState.PARKED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="park",
        )

    async def test_stationary_from_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 and getting set to STOPPING_BRAKING while moving.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(3.0, 8.0, 0.0, mtdome.LlcMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=2.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_stationary_from_crawling_after_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10, start crawling and then getting stopped while crawling.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
            ExpectedState(3.0, 10.05, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 10.15, 0.0, mtdome.LlcMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_stationary_from_crawling(self) -> None:
        """Test the AmcsStatus when crawling and then getting
        stopped.
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 11.0, crawl_velocity, mtdome.LlcMotionState.CRAWLING),
        ]
        await self.verify_amcs(
            command="crawl",
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 14.0, 0.0, mtdome.LlcMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_exit_fault(self) -> None:
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

        # This sets the status of the state machine to ERROR.
        drives_in_error = [1, 1, 0, 0, 0]
        expected_drive_error_state = [True, True, False, False, False]
        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 1.1
        await self.amcs.set_fault(current_tai, drives_in_error)
        assert (
            self.amcs.azimuth_motion.drives_in_error_state == expected_drive_error_state
        )
        await self.verify_amcs_state(
            tai=current_tai,
            expected_position=4.4,
            expected_velocity=0.0,
            expected_motion_state=mtdome.LlcMotionState.ERROR,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 2.0

        # Now call exit_fault. This will fail because there still are drives at
        # fault.
        with pytest.raises(RuntimeError):
            await self.amcs.exit_fault(current_tai)

        # Reset the drives.
        expected_drive_error_state = [False, False, False, False, False]
        reset = [1, 1, 0, 0, 0]
        await self.amcs.reset_drives_az(current_tai, reset)
        assert (
            self.amcs.azimuth_motion.drives_in_error_state == expected_drive_error_state
        )

        # Now call exit_fault which will not fail because the drives have been
        # reset.
        await self.amcs.exit_fault(current_tai)
        await self.verify_amcs_state(
            tai=current_tai,
            expected_position=4.4,
            expected_velocity=0.0,
            expected_motion_state=mtdome.LlcMotionState.STATIONARY,
        )
        assert (
            self.amcs.azimuth_motion.drives_in_error_state == expected_drive_error_state
        )
        assert self.amcs.azimuth_motion.motion_state_in_error is False

    async def test_calibrate_az(self) -> None:
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, mtdome.LlcMotionState.MOVING),
        ]
        await self.verify_amcs(
            command="move",
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 1.1
        with pytest.raises(RuntimeError):
            await self.amcs.calibrate_az(current_tai)

        await self.verify_amcs_state(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=10.0,
            expected_velocity=0.0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 3.0
        await self.amcs.calibrate_az(current_tai)

        await self.verify_amcs_state(
            tai=current_tai,
            expected_position=0.0,
            expected_velocity=0.0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

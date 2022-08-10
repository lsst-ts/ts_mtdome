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
from lsst.ts import mtdome
from lsst.ts.mtdome.mock_llc.amcs import (
    POWER_PER_MOTOR_CRAWLING,
    POWER_PER_MOTOR_MOVING,
)
from lsst.ts.mtdome.mock_llc.mock_motion.azimuth_motion import NUM_MOTORS

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

# The maximum AZ rotation speed (rad/s)
MAX_SPEED = math.radians(4.0)
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
            The start position of the azimuth motion.
        max_speed: `float`
            The maximum allowed speed.
        start_tai: `float`
            The start TAI time.
        """
        self.amcs = mtdome.mock_llc.AmcsStatus(start_tai=start_tai)
        azimuth_motion = mtdome.mock_llc.AzimuthMotion(
            start_position=start_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        self.amcs.azimuth_motion = azimuth_motion

    async def verify_amcs(
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
            The expected position at the given TAI time.
        expected_velocity: `float`
            The expected velocity at the given TAI time.
        expected_motion_state: `float`
            The expected motion state at the given TAI time.
        """
        await self.amcs.determine_status(current_tai=tai)
        assert expected_position == pytest.approx(
            self.amcs.llc_status["positionActual"]
        )
        assert expected_velocity == pytest.approx(
            self.amcs.llc_status["velocityActual"]
        )
        assert expected_motion_state.name == self.amcs.llc_status["status"]["status"]
        expected_drive_current: list[float] = [0.0] * NUM_MOTORS
        if expected_motion_state == mtdome.LlcMotionState.MOVING:
            expected_drive_current = [POWER_PER_MOTOR_MOVING] * NUM_MOTORS
        elif expected_motion_state == mtdome.LlcMotionState.CRAWLING:
            expected_drive_current = [POWER_PER_MOTOR_CRAWLING] * NUM_MOTORS
        assert expected_drive_current == self.amcs.llc_status["driveCurrentActual"]

    async def test_move_zero_ten_pos(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 degrees and then crawl in positive direction.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        for delta_t in [1.0, 2.0]:
            await self.verify_amcs(
                tai=START_TAI + START_MOTORS_ADD_DURATION + delta_t,
                expected_position=MAX_SPEED * delta_t,
                expected_velocity=MAX_SPEED,
                expected_motion_state=mtdome.LlcMotionState.MOVING,
            )

        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=math.radians(10.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0,
            expected_position=math.radians(10.15),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_zero_ten_neg(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 degrees and then crawl in negative direction.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(-0.1)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        for delta_t in [1.0, 2.0]:
            await self.verify_amcs(
                tai=START_TAI + START_MOTORS_ADD_DURATION + delta_t,
                expected_position=MAX_SPEED * delta_t,
                expected_velocity=MAX_SPEED,
                expected_motion_state=mtdome.LlcMotionState.MOVING,
            )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=math.radians(10.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0,
            expected_position=math.radians(9.85),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_ten_zero_pos(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 0 degrees and then crawl in positive direction.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        target_position = 0.0
        crawl_velocity = math.radians(0.1)
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(6.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(2.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=math.radians(0.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0,
            expected_position=math.radians(0.15),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_ten_zero_neg(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 0 degrees and then crawl in negative direction.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        target_position = 0.0
        crawl_velocity = math.radians(-0.1)
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(6.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(2.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=math.radians(0.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0,
            expected_position=math.radians(359.85),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_ten_threefifty_pos(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in positive direction.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        target_position = math.radians(350.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position - 2 * math.pi) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(6.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(2.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(358.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(350.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 6.0,
            expected_position=math.radians(350.1),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_ten_threefifty_neg(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in negative direction.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        target_position = math.radians(350.0)
        crawl_velocity = math.radians(-0.1)
        expected_duration = START_MOTORS_ADD_DURATION + math.fabs(
            (target_position - start_position - 2 * math.pi) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(6.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(2.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(358.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(350.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 6.0,
            expected_position=math.radians(349.9),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_threefifty_ten_pos(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in positive direction.
        """
        start_position = math.radians(350.0)
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = math.fabs(
            START_MOTORS_ADD_DURATION
            + (target_position - start_position + 2 * math.pi) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(354.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(358.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(2.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(10.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 6.0,
            expected_position=math.radians(10.1),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_move_threefifty_ten_neg(self) -> None:
        """Test the AmcsStatus when moving from position 10 to
        position 350 degrees then crawl in negative direction.
        """
        start_position = math.radians(350.0)
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(-0.1)
        expected_duration = math.fabs(
            START_MOTORS_ADD_DURATION
            + (target_position - start_position + 2 * math.pi) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(354.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(358.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(2.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(10.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 6.0,
            expected_position=math.radians(9.9),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_crawl_pos(self) -> None:
        """Test the AmcsStatus when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        start_position = math.radians(350.0)
        start_tai = START_TAI
        crawl_velocity = math.radians(1.0)
        expected_duration = START_MOTORS_ADD_DURATION
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.crawlAz(velocity=crawl_velocity, start_tai=start_tai)
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(351.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(352.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 10.0,
            expected_position=math.radians(0.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 11.0,
            expected_position=math.radians(1.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 20.0,
            expected_position=math.radians(10.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 21.0,
            expected_position=math.radians(11.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_crawl_neg(self) -> None:
        """Test the AmcsStatus when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        crawl_velocity = math.radians(-1.0)
        expected_duration = START_MOTORS_ADD_DURATION
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.crawlAz(velocity=crawl_velocity, start_tai=start_tai)
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(9.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0,
            expected_position=math.radians(8.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 10.0,
            expected_position=math.radians(0.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 11.0,
            expected_position=math.radians(359.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 20.0,
            expected_position=math.radians(350.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 21.0,
            expected_position=math.radians(349.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

    async def test_stop_from_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 and getting stopped while moving.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = 0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.amcs.stopAz(start_tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(8.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_stop_from_crawling_after_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10, start crawling and then getting stopped while crawling.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(10.05),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.amcs.stopAz(start_tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(10.15),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_stop_from_crawling(self) -> None:
        """Test the AmcsStatus when crawling and then getting
        stopped.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        crawl_velocity = math.radians(1.0)
        expected_duration = START_MOTORS_ADD_DURATION
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.crawlAz(velocity=crawl_velocity, start_tai=start_tai)
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(11.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.amcs.stopAz(start_tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(14.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_park_from_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 and getting parked while moving.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = 0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )

        start_tai = START_TAI + START_MOTORS_ADD_DURATION + 1.0
        await self.amcs.park(start_tai=start_tai)
        await self.verify_amcs(
            tai=start_tai,
            expected_position=math.radians(4.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=start_tai + 3.0,
            expected_position=math.radians(0.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.PARKED,
        )

    async def test_park_from_crawling_after_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10, start crawling and then getting parked while crawling.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(10.05),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

        start_tai = START_TAI + START_MOTORS_ADD_DURATION + 4.0
        await self.amcs.park(start_tai=start_tai)
        await self.verify_amcs(
            tai=start_tai + 1.0,
            expected_position=math.radians(6.15),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=start_tai + 2.0,
            expected_position=math.radians(2.15),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=start_tai + 3.0,
            expected_position=math.radians(0.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.PARKED,
        )

    async def test_park_from_crawling(self) -> None:
        """Test the AmcsStatus when crawling and then getting
        parked.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        crawl_velocity = math.radians(1.0)
        expected_duration = START_MOTORS_ADD_DURATION
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.crawlAz(velocity=crawl_velocity, start_tai=start_tai)
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(11.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

        start_tai = START_TAI + START_MOTORS_ADD_DURATION + 4.0
        await self.amcs.park(start_tai=start_tai)
        await self.verify_amcs(
            tai=start_tai + 1.0,
            expected_position=math.radians(10.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=start_tai + 2.0,
            expected_position=math.radians(6.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=start_tai + 3.0,
            expected_position=math.radians(2.0),
            expected_velocity=-MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=start_tai + 5.0,
            expected_position=math.radians(0.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.PARKED,
        )

    async def test_stationary_from_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10 and getting set to STOPPING_BRAKING while moving.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = 0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.amcs.go_stationary(
            start_tai=START_TAI + START_MOTORS_ADD_DURATION + 2.0
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(8.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STATIONARY,
        )

    async def test_stationary_from_crawling_after_moving(self) -> None:
        """Test the AmcsStatus when moving from position 0 to
        position 10, start crawling and then getting stopped while crawling.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 3.0,
            expected_position=math.radians(10.05),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.amcs.go_stationary(
            start_tai=START_TAI + START_MOTORS_ADD_DURATION + 4.0
        )
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 5.0,
            expected_position=math.radians(10.15),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STATIONARY,
        )

    async def test_stationary_from_crawling(self) -> None:
        """Test the AmcsStatus when crawling and then getting
        stopped.
        """
        start_position = math.radians(10.0)
        start_tai = START_TAI
        crawl_velocity = math.radians(1.0)
        expected_duration = START_MOTORS_ADD_DURATION
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.crawlAz(velocity=crawl_velocity, start_tai=start_tai)
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(11.0),
            expected_velocity=crawl_velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )

        start_tai = START_TAI + START_MOTORS_ADD_DURATION + 4.0
        await self.amcs.go_stationary(start_tai=start_tai)
        await self.verify_amcs(
            tai=start_tai + 1.0,
            expected_position=math.radians(14.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STATIONARY,
        )

    async def test_exit_fault(self) -> None:
        start_position = 0.0
        start_tai = START_TAI
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )

        # This sets the status of the state machine to ERROR.
        drives_in_error = [1, 1, 0, 0, 0]
        expected_drive_error_state = [True, True, False, False, False]
        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 1.1
        await self.amcs.set_fault(current_tai, drives_in_error)
        assert (
            self.amcs.azimuth_motion.drives_in_error_state == expected_drive_error_state
        )
        await self.verify_amcs(
            tai=current_tai,
            expected_position=math.radians(4.4),
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
        await self.verify_amcs(
            tai=current_tai,
            expected_position=math.radians(4.4),
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
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.0)
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        await self.prepare_amcs(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        duration = await self.amcs.moveAz(
            position=target_position, velocity=crawl_velocity, start_tai=start_tai
        )
        assert expected_duration == pytest.approx(duration)
        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 1.0,
            expected_position=math.radians(4.0),
            expected_velocity=MAX_SPEED,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 1.1
        with pytest.raises(RuntimeError):
            await self.amcs.calibrate_az(current_tai)

        await self.verify_amcs(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=math.radians(10.0),
            expected_velocity=0.0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 3.0
        await self.amcs.calibrate_az(current_tai)

        await self.verify_amcs(
            tai=current_tai,
            expected_position=math.radians(0.0),
            expected_velocity=0.0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

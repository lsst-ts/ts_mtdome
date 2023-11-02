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

import math
import unittest

import pytest
from expected_state import ExpectedState
from lsst.ts import mtdome
from lsst.ts.xml.enums.MTDome import MotionState

# The maximum AZ rotation speed (deg/s)
MAX_SPEED = 4.0
START_TAI = 10001.0
START_MOTORS_ADD_DURATION = 5.5


class AzimuthMotionTestCase(unittest.IsolatedAsyncioTestCase):
    async def prepare_azimuth_motion(
        self, start_position: float, max_speed: float, start_tai: float
    ) -> None:
        """Prepare the AzimuthMotion for future commands.

        Parameters
        ----------
        start_position: `float`
            The start position of the azimuth motion.
        max_speed: `float`
            The maximum allowed speed.
        start_tai: `float`
            The start TAI time.
        """
        self.azimuth_motion = mtdome.mock_llc.AzimuthMotion(
            start_position=math.radians(start_position),
            max_speed=math.radians(max_speed),
            start_tai=start_tai,
        )

    async def verify_azimuth_state(
        self,
        tai: float,
        expected_position: float,
        expected_velocity: float,
        expected_motion_state: MotionState,
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
        (
            position,
            velocity,
            motion_state,
        ) = self.azimuth_motion.get_position_velocity_and_motion_state(tai)
        assert pytest.approx(math.degrees(position)) == expected_position
        assert pytest.approx(math.degrees(velocity)) == expected_velocity
        assert motion_state == expected_motion_state

    async def verify_duration(
        self,
        target_position: float,
        crawl_velocity: float,
        start_tai: float,
        motion_state: MotionState,
        expected_duration: float,
    ) -> None:
        duration = self.azimuth_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=math.radians(target_position),
            crawl_velocity=math.radians(crawl_velocity),
            motion_state=motion_state,
        )
        assert pytest.approx(duration) == expected_duration

    async def verify_halt(
        self,
        start_tai: float,
        expected_states: list[ExpectedState],
        command: str,
    ) -> None:
        func = getattr(self.azimuth_motion, command)
        func(start_tai=START_TAI + START_MOTORS_ADD_DURATION + start_tai)
        for expected_state in expected_states:
            tai = expected_state.tai
            await self.verify_azimuth_state(
                tai=START_TAI + START_MOTORS_ADD_DURATION + tai,
                expected_position=expected_state.position,
                expected_velocity=expected_state.velocity,
                expected_motion_state=expected_state.motion_state,
            )

    async def verify_azimuth(
        self,
        commanded_state: MotionState,
        start_position: float,
        target_position: float,
        max_speed: float,
        crawl_velocity: float,
        expected_duration: float,
        expected_states: list[ExpectedState],
        start_tai: float,
        prepare_azimuth_motion: bool = True,
    ) -> None:
        if prepare_azimuth_motion:
            await self.prepare_azimuth_motion(
                start_position=start_position,
                max_speed=max_speed,
                start_tai=start_tai,
            )
        await self.verify_duration(
            target_position,
            crawl_velocity,
            start_tai,
            commanded_state,
            expected_duration,
        )
        for expected_state in expected_states:
            tai = expected_state.tai
            await self.verify_azimuth_state(
                tai=START_TAI + START_MOTORS_ADD_DURATION + tai,
                expected_position=expected_state.position,
                expected_velocity=expected_state.velocity,
                expected_motion_state=expected_state.motion_state,
            )

    async def test_move_zero_ten_pos(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 8.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.5, 10.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(4.0, 10.15, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_zero_ten_pos_in_two_steps(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
        position 10 degrees in two steps and then stop.
        """
        start_position = 0.0
        start_tai = START_TAI
        target_position_1 = 5.0
        target_position_2 = 10.0
        crawl_velocity = 0.0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position_1 - start_position) / MAX_SPEED
        )
        expected_states_1 = [
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(1.25, 5.0, 0.0, MotionState.STOPPED),
        ]
        expected_states_2 = [
            ExpectedState(2.0, 8.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 10.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position_1,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states_1,
            start_tai=start_tai,
        )
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=target_position_1,
            target_position=target_position_2,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=1.25,
            expected_states=expected_states_2,
            start_tai=start_tai + expected_duration,
            prepare_azimuth_motion=False,
        )

    async def test_move_zero_ten_neg(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 8.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.5, 10.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(4.0, 9.85, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_zero_pos(self) -> None:
        """Test the AzimuthMotion when moving from position 10 to
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
            ExpectedState(1.0, 6.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.5, 0.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(4.0, 0.15, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_zero_neg(self) -> None:
        """Test the AzimuthMotion when moving from position 10 to
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
            ExpectedState(1.0, 6.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.5, 0.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(4.0, 359.85, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_threefifty_pos(self) -> None:
        """Test the AzimuthMotion when moving from position 10 to
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
            ExpectedState(1.0, 6.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 358.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(5.0, 350.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(6.0, 350.1, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_threefifty_neg(self) -> None:
        """Test the AzimuthMotion when moving from position 10 to
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
            ExpectedState(1.0, 6.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 2.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 358.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(5.0, 350.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(6.0, 349.9, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_threefifty_ten_pos(self) -> None:
        """Test the AzimuthMotion when moving from position 10 to
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
            ExpectedState(1.0, 354.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 358.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 2.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(5.0, 10.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(6.0, 10.1, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_threefifty_ten_neg(self) -> None:
        """Test the AzimuthMotion when moving from position 10 to
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
            ExpectedState(1.0, 354.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(2.0, 358.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 2.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(5.0, 10.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(6.0, 9.9, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_crawl_pos(self) -> None:
        """Test the AzimuthMotion when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        start_position = 350.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 351.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(2.0, 352.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(10.0, 0.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(11.0, 1.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(20.0, 10.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(21.0, 11.0, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_crawl_neg(self) -> None:
        """Test the AzimuthMotion when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = -1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 9.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(2.0, 8.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(10.0, 0.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(11.0, 359.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(20.0, 350.0, crawl_velocity, MotionState.CRAWLING),
            ExpectedState(21.0, 349.0, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_stop_from_moving(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(3.0, 8.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=2.0,
            expected_states=expected_states,
            command="stop",
        )

    async def test_stop_from_crawling_after_moving(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 10.05, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 10.15, 0.0, MotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="stop",
        )

    async def test_stop_from_crawling(self) -> None:
        """Test the AzimuthMotion when crawling and then getting
        stopped.
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 11.0, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 14.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="stop",
        )

    async def test_park_from_moving(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(1.0, 4.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 0.0, 0.0, MotionState.PARKED),
        ]
        await self.verify_halt(
            start_tai=1.0,
            expected_states=expected_states,
            command=mtdome.CommandName.PARK,
        )

    async def test_park_from_crawling_after_moving(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 10.05, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 6.15, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(6.0, 2.15, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(7.0, 0.0, 0.0, MotionState.PARKED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command=mtdome.CommandName.PARK,
        )

    async def test_park_from_crawling(self) -> None:
        """Test the AzimuthMotion when crawling and then getting
        parked.
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 11.0, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 10.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(6.0, 6.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(7.0, 2.0, -MAX_SPEED, MotionState.MOVING),
            ExpectedState(8.0, 0.0, 0.0, MotionState.PARKED),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command=mtdome.CommandName.PARK,
        )

    async def test_stationary_from_moving(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(3.0, 8.0, 0.0, mtdome.InternalMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=2.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_stationary_from_crawling_after_moving(self) -> None:
        """Test the AzimuthMotion when moving from position 0 to
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
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
            ExpectedState(3.0, 10.05, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            target_position=target_position,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 10.15, 0.0, mtdome.InternalMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_stationary_from_crawling(self) -> None:
        """Test the AzimuthMotion when crawling and then getting
        stopped.
        """
        start_position = 10.0
        start_tai = START_TAI
        crawl_velocity = 1.0
        expected_duration = START_MOTORS_ADD_DURATION
        expected_states = [
            ExpectedState(1.0, 11.0, crawl_velocity, MotionState.CRAWLING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            target_position=math.inf,
            max_speed=MAX_SPEED,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(5.0, 14.0, 0.0, mtdome.InternalMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=4.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_too_high(self) -> None:
        """Test the AzimuthMotion when trying to crawl at a too high
        speed.
        """
        start_position = 10.0
        start_tai = START_TAI
        target_position = 11.0
        crawl_velocity = 5.0
        expected_duration = 0.0
        await self.prepare_azimuth_motion(
            start_position=start_position,
            max_speed=MAX_SPEED,
            start_tai=start_tai,
        )
        try:
            await self.verify_duration(
                start_tai=start_tai,
                target_position=target_position,
                crawl_velocity=crawl_velocity,
                expected_duration=expected_duration,
                motion_state=MotionState.MOVING,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

    async def test_exit_fault(self) -> None:
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.1
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
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
        self.azimuth_motion.set_fault(current_tai, drives_in_error)
        assert self.azimuth_motion.drives_in_error_state == expected_drive_error_state
        await self.verify_azimuth_state(
            tai=current_tai,
            expected_position=4.4,
            expected_velocity=0.0,
            expected_motion_state=MotionState.ERROR,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 2.0

        # Now call exit_fault. This will fail because there still are drives at
        # fault.
        with pytest.raises(RuntimeError):
            self.azimuth_motion.exit_fault(current_tai)

        # Reset the drives.
        expected_drive_error_state = [False, False, False, False, False]
        reset = [1, 1, 0, 0, 0]
        self.azimuth_motion.reset_drives(current_tai, reset)
        assert self.azimuth_motion.drives_in_error_state == expected_drive_error_state

        # Now call exit_fault which will not fail because the drives have been
        # reset.
        self.azimuth_motion.exit_fault(current_tai)
        await self.verify_azimuth_state(
            tai=current_tai,
            expected_position=4.4,
            expected_velocity=0.0,
            expected_motion_state=mtdome.InternalMotionState.STATIONARY,
        )
        assert self.azimuth_motion.drives_in_error_state == expected_drive_error_state
        assert self.azimuth_motion.motion_state_in_error is False

    async def test_calibrate_az(self) -> None:
        start_position = 0.0
        start_tai = START_TAI
        target_position = 10.0
        crawl_velocity = 0.0
        expected_duration = (
            START_MOTORS_ADD_DURATION + (target_position - start_position) / MAX_SPEED
        )
        expected_states = [
            ExpectedState(1.0, 4.0, MAX_SPEED, MotionState.MOVING),
        ]
        await self.verify_azimuth(
            commanded_state=MotionState.MOVING,
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
            self.azimuth_motion.calibrate_az(current_tai)

        await self.verify_azimuth_state(
            tai=START_TAI + START_MOTORS_ADD_DURATION + 2.5,
            expected_position=10.0,
            expected_velocity=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

        current_tai = START_TAI + START_MOTORS_ADD_DURATION + 3.0
        self.azimuth_motion.calibrate_az(current_tai)

        await self.verify_azimuth_state(
            tai=current_tai,
            expected_position=0.0,
            expected_velocity=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

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

import math
import unittest

import pytest
from expected_state import ExpectedState
from lsst.ts import mtdome
from lsst.ts.idl.enums.MTDome import MotionState

START_TAI = 10001.0
MIN_POSITION = 0
MAX_POSITION = 90


class ElevationMotionTestCase(unittest.IsolatedAsyncioTestCase):
    async def prepare_elevation_motion(
        self,
        start_position: float,
        min_position: float,
        max_position: float,
        max_speed: float,
        start_tai: float,
    ) -> None:
        """Prepare the ElevationMotion for future commands.

        Parameters
        ----------
        start_position: `float`
            The initial position.
        min_position: `float`
            The minimum allowed position.
        max_position: `float`
            The maximum allowed position.
        max_speed: `float`
            The maximum allowed speed.
        start_tai: `float`
            The current TAI time.
        """
        self.elevation_motion = mtdome.mock_llc.ElevationMotion(
            start_position=math.radians(start_position),
            min_position=math.radians(min_position),
            max_position=math.radians(max_position),
            max_speed=math.radians(max_speed),
            start_tai=start_tai,
        )

    async def verify_elevation_state(
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
        ) = self.elevation_motion.get_position_velocity_and_motion_state(tai)
        assert pytest.approx(math.degrees(position)) == expected_position
        assert pytest.approx(math.degrees(velocity)) == expected_velocity
        assert motion_state == expected_motion_state

    async def verify_elevation_motion_duration(
        self,
        start_tai: float,
        target_position: float,
        crawl_velocity: float,
        motion_state: MotionState,
        expected_duration: float,
    ) -> None:
        """Verify that the ElevationMotion computes the correct duration.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position.
        crawl_velocity: `float`
            The velocity for the crawl.
        expected_duration: `float`
            The expected duration.
        motion_state: `MotionState`
            The commanded MotionState.
        """
        duration = self.elevation_motion.set_target_position_and_velocity(
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
        func = getattr(self.elevation_motion, command)
        func(start_tai=START_TAI + start_tai)
        for expected_state in expected_states:
            tai = expected_state.tai
            await self.verify_elevation_state(
                tai=START_TAI + tai,
                expected_position=expected_state.position,
                expected_velocity=expected_state.velocity,
                expected_motion_state=expected_state.motion_state,
            )

    async def verify_elevation(
        self,
        commanded_state: MotionState,
        start_position: float,
        min_position: float,
        max_position: float,
        target_position: float,
        max_speed: float,
        crawl_velocity: float,
        expected_duration: float,
        expected_states: list[ExpectedState],
        start_tai: float,
    ) -> None:
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai,
            target_position,
            crawl_velocity,
            commanded_state,
            expected_duration,
        )
        for expected_state in expected_states:
            tai = expected_state.tai
            await self.verify_elevation_state(
                tai=START_TAI + tai,
                expected_position=expected_state.position,
                expected_velocity=expected_state.velocity,
                expected_motion_state=expected_state.motion_state,
            )

    async def test_move_zero_ten(self) -> None:
        """Test the ElevationMotion when moving from position 0 to
        position 10.
        """
        start_position = 0.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        target_position = 10.0
        velocity = 3.5
        expected_duration = (target_position - start_position) / velocity
        expected_states = [
            ExpectedState(1.0, 3.5, velocity, MotionState.MOVING),
            ExpectedState(2.5, 8.75, velocity, MotionState.MOVING),
            ExpectedState(3.0, 10.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_elevation(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            target_position=target_position,
            max_speed=max_speed,
            crawl_velocity=0.0,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_move_ten_zero(self) -> None:
        """Test the ElevationMotion when moving from position 10 to
        position 0.
        """
        start_position = 10.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        target_position = 0.0
        velocity = -3.5
        expected_duration = (target_position - start_position) / velocity
        expected_states = [
            ExpectedState(1.0, 6.5, velocity, MotionState.MOVING),
            ExpectedState(2.5, 1.25, velocity, MotionState.MOVING),
            ExpectedState(3.0, 0.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_elevation(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            target_position=target_position,
            max_speed=max_speed,
            crawl_velocity=0.0,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_crawl_pos(self) -> None:
        """Test the ElevationMotion when crawling in positive direction."""
        start_position = 0.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        velocity = 1.0
        expected_duration = 0
        expected_states = [
            ExpectedState(1.0, 1.0, velocity, MotionState.CRAWLING),
            ExpectedState(2.5, 2.5, velocity, MotionState.CRAWLING),
            ExpectedState(10.1, 10.1, velocity, MotionState.CRAWLING),
            ExpectedState(89.0, 89.0, velocity, MotionState.CRAWLING),
            ExpectedState(90.0, 90.0, 0.0, MotionState.STOPPED),
            ExpectedState(91.0, 90.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_elevation(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            target_position=math.inf,
            max_speed=max_speed,
            crawl_velocity=velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_crawl_neg(self) -> None:
        """Test the ElevationMotion when crawling from position 10 to
        position 0.
        """
        start_position = 10.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        velocity = -1.0
        expected_duration = 0
        expected_states = [
            ExpectedState(1.0, 9.0, velocity, MotionState.CRAWLING),
            ExpectedState(2.5, 7.5, velocity, MotionState.CRAWLING),
            ExpectedState(10.1, 0.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_elevation(
            commanded_state=MotionState.CRAWLING,
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            target_position=math.inf,
            max_speed=max_speed,
            crawl_velocity=velocity,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )

    async def test_stop(self) -> None:
        """Test the ElevationMotion when moving from position 0 to
        position 10 and then gets stopped.
        """
        start_position = 0.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        target_position = 10.0
        velocity = 3.5
        expected_duration = (target_position - start_position) / velocity
        expected_states = [
            ExpectedState(1.0, 3.5, velocity, MotionState.MOVING),
        ]
        await self.verify_elevation(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            target_position=target_position,
            max_speed=max_speed,
            crawl_velocity=0.0,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(3.0, 7.0, 0.0, MotionState.STOPPED),
        ]
        await self.verify_halt(
            start_tai=2.0,
            expected_states=expected_states,
            command="stop",
        )

    async def test_stationary(self) -> None:
        """Test the ElevationMotion when moving from position 0 to
        position 10 and then gets stopped.
        """
        start_position = 0.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        target_position = 10.0
        velocity = 3.5
        expected_duration = (target_position - start_position) / velocity
        expected_states = [
            ExpectedState(1.0, 3.5, velocity, MotionState.MOVING),
        ]
        await self.verify_elevation(
            commanded_state=MotionState.MOVING,
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            target_position=target_position,
            max_speed=max_speed,
            crawl_velocity=0.0,
            expected_duration=expected_duration,
            expected_states=expected_states,
            start_tai=start_tai,
        )
        expected_states = [
            ExpectedState(3.0, 7.0, 0.0, mtdome.InternalMotionState.STATIONARY),
        ]
        await self.verify_halt(
            start_tai=2.0,
            expected_states=expected_states,
            command="go_stationary",
        )

    async def test_too_low(self) -> None:
        """Test the ElevationMotion when trying to move to a too low
        position.
        """
        start_position = 10.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        target_position = -91.0
        velocity = -3.5
        expected_duration = (target_position - start_position) / velocity
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        try:
            await self.verify_elevation_motion_duration(
                start_tai=start_tai,
                target_position=target_position,
                crawl_velocity=velocity,
                expected_duration=expected_duration,
                motion_state=MotionState.MOVING,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

    async def test_too_high(self) -> None:
        """Test the ElevationMotion when trying to move to a too high
        position.
        """
        start_position = 10.0
        start_tai = START_TAI
        min_position = MIN_POSITION
        max_position = MAX_POSITION
        max_speed = 3.5
        target_position = 91.0
        velocity = 3.5
        expected_duration = (target_position - start_position) / velocity
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        try:
            await self.verify_elevation_motion_duration(
                start_tai=start_tai,
                target_position=target_position,
                crawl_velocity=velocity,
                expected_duration=expected_duration,
                motion_state=MotionState.MOVING,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

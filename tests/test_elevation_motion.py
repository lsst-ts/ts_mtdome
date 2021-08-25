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

from lsst.ts import mtdome

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

_start_tai = 10001.0
_MIN_POSITION = 0
_MAX_POSITION = math.radians(90)


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
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )

    async def verify_elevation_motion_duration(
        self,
        start_tai: float,
        target_position: float,
        velocity: float,
        expected_duration: float,
        motion_state: mtdome.LlcMotionState,
    ) -> None:
        """Verify that the ElevationMotion computes the correct duration.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position.
        velocity: `float`
            The velocity for the motion.
        expected_duration: `float`
            The expected duration.
        motion_state: `MotionState`
            The commanded mtdome.LlcMotionState.
        """
        duration = self.elevation_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=target_position,
            crawl_velocity=velocity,
            motion_state=motion_state,
        )
        self.assertEqual(expected_duration, duration)

    async def verify_elevation_motion(
        self,
        tai: float,
        expected_position: float,
        expected_velocity: float,
        expected_motion_state: mtdome.LlcMotionState,
    ) -> None:
        """Verify the position of the ElevationMotion at the given TAI
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
        (
            position,
            velocity,
            motion_state,
        ) = self.elevation_motion.get_position_velocity_and_motion_state(tai)
        self.assertAlmostEqual(expected_position, position)
        self.assertAlmostEqual(expected_velocity, velocity)
        self.assertEqual(expected_motion_state, motion_state)

    async def test_move_zero_ten(self) -> None:
        """Test the ElevationMotion when moving from position 0 to
        position 10.
        """
        start_position = 0.0
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = math.radians(10.0)
        velocity = math.radians(3.5)
        expected_duration = (target_position - start_position) / velocity
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
            motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 1.0,
            expected_position=math.radians(3.5),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 2.5,
            expected_position=math.radians(8.75),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 3.0,
            expected_position=math.radians(10.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_move_ten_zero(self) -> None:
        """Test the ElevationMotion when moving from position 10 to
        position 0.
        """
        start_position = math.radians(10.0)
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = 0.0
        velocity = math.radians(-3.5)
        expected_duration = (target_position - start_position) / velocity
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
            motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 1.0,
            expected_position=math.radians(6.5),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 2.5,
            expected_position=math.radians(1.25),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 3.0,
            expected_position=0.0,
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_crawl_pos(self) -> None:
        """Test the ElevationMotion when crawling in positive direction."""
        start_position = 0.0
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = math.radians(10.0)
        velocity = math.radians(1.0)
        expected_duration = 0
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
            motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 1.0,
            expected_position=math.radians(1.0),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 2.5,
            expected_position=math.radians(2.5),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 10.1,
            expected_position=math.radians(10.1),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 89.0,
            expected_position=math.radians(89.0),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 90.0,
            expected_position=math.radians(90.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 91.0,
            expected_position=math.radians(90.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_crawl_neg(self) -> None:
        """Test the ElevationMotion when crawling from position 10 to
        position 0.
        """
        start_position = math.radians(10.0)
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = 0.0
        velocity = math.radians(-1.0)
        expected_duration = 0
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
            motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 1.0,
            expected_position=math.radians(9.0),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 2.5,
            expected_position=math.radians(7.5),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.CRAWLING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 10.1,
            expected_position=math.radians(0.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_stop(self) -> None:
        """Test the ElevationMotion when moving from position 0 to
        position 10 and then gets stopped.
        """
        start_position = 0.0
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = math.radians(10.0)
        velocity = math.radians(3.5)
        expected_duration = (target_position - start_position) / velocity
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
            motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 1.0,
            expected_position=math.radians(3.5),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        self.elevation_motion.stop(start_tai=_start_tai + 2.0)
        await self.verify_elevation_motion(
            tai=_start_tai + 3.0,
            expected_position=math.radians(7.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STOPPED,
        )

    async def test_stationary(self) -> None:
        """Test the ElevationMotion when moving from position 0 to
        position 10 and then gets stopped.
        """
        start_position = 0.0
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = math.radians(10.0)
        velocity = math.radians(3.5)
        expected_duration = (target_position - start_position) / velocity
        await self.prepare_elevation_motion(
            start_position=start_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            start_tai=start_tai,
        )
        await self.verify_elevation_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
            motion_state=mtdome.LlcMotionState.MOVING,
        )
        await self.verify_elevation_motion(
            tai=_start_tai + 1.0,
            expected_position=math.radians(3.5),
            expected_velocity=velocity,
            expected_motion_state=mtdome.LlcMotionState.MOVING,
        )
        self.elevation_motion.go_stationary(start_tai=_start_tai + 2.0)
        await self.verify_elevation_motion(
            tai=_start_tai + 3.0,
            expected_position=math.radians(7.0),
            expected_velocity=0,
            expected_motion_state=mtdome.LlcMotionState.STATIONARY,
        )

    async def test_too_low(self) -> None:
        """Test the ElevationMotion when trying to move to a too low
        position.
        """
        start_position = math.radians(10.0)
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = math.radians(-91.0)
        velocity = math.radians(-3.5)
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
                velocity=velocity,
                expected_duration=expected_duration,
                motion_state=mtdome.LlcMotionState.MOVING,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

    async def test_too_high(self) -> None:
        """Test the ElevationMotion when trying to move to a too high
        position.
        """
        start_position = math.radians(10.0)
        start_tai = _start_tai
        min_position = _MIN_POSITION
        max_position = _MAX_POSITION
        max_speed = math.radians(3.5)
        target_position = math.radians(91.0)
        velocity = math.radians(3.5)
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
                velocity=velocity,
                expected_duration=expected_duration,
                motion_state=mtdome.LlcMotionState.MOVING,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

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

import asynctest
import logging

from lsst.ts.Dome.mock_llc_statuses.mock_motion import ElevationMotion
from lsst.ts.idl.enums.Dome import MotionState

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

_COMMANDED_TAI = 10001.0


class ElevationMotionTestCase(asynctest.TestCase):
    async def prepare_elevation_motion(
        self, initial_position, min_position, max_position, max_speed, current_tai
    ):
        """Prepare the ElevationMotion for future commands.

        Parameters
        ----------
        initial_position: `float`
            The initial position.
        min_position: `float`
            The minimum allowed position.
        max_position: `float`
            The maximum allowed position.
        max_speed: `float`
            The maximum allowed speed.
        current_tai: `float`
            The current TAI time.
        """
        self.elevation_motion = ElevationMotion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=current_tai,
        )

    async def verify_elevation_motion_duration(
        self, commanded_tai, target_position, velocity, expected_duration,
    ):
        """Verify that the ElevationMotion computes the correct duration.

        Parameters
        ----------
        commanded_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position.
        velocity: `float`
            The velocity for the motion.
        expected_duration: `float`
            The expected duration.
        """
        duration = self.elevation_motion.set_target_position_and_velocity(
            commanded_tai=commanded_tai,
            target_position=target_position,
            velocity=velocity,
        )
        self.assertEqual(expected_duration, duration)

    async def verify_elevation_motion_position(
        self, tai, expected_position, expected_motion_state
    ):
        """Verify the position of the ElevationMotion at the given TAI
        time.

        Parameters
        ----------
        tai: `float`
            The TAI time to compute the position for.
        expected_position: `float`
            The expected position at the given TAI time.
        expected_motion_state: `float`
            The expected motion state at the given TAI time.
        """
        position, motion_state = self.elevation_motion.get_position_and_motion_state(
            tai
        )
        self.assertAlmostEqual(expected_position, position)
        self.assertEqual(expected_motion_state, motion_state)

    async def test_move_zero_ten(self):
        """Test the ElevationMotion when moving from position 0 to
        position 10.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = 10.0
        velocity = 3.5
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_elevation_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=3.5,
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=8.75,
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=10.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_move_ten_zero(self):
        """Test the ElevationMotion when moving from position 10 to
        position 0.
        """
        initial_position = 10.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = 0.0
        velocity = -3.5
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_elevation_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=6.5,
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=1.25,
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_crawl_pos(self):
        """Test the ElevationMotion when crawling in positive direction.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = 10.0
        velocity = 1.0
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_elevation_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=1.0,
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=2.5,
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 10.1,
            expected_position=10.1,
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 89.0,
            expected_position=89.0,
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 90.0,
            expected_position=90.0,
            expected_motion_state=MotionState.STOPPED,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 91.0,
            expected_position=90.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_crawl_neg(self):
        """Test the ElevationMotion when crawling from position 10 to
        position 0.
        """
        initial_position = 10.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = 0.0
        velocity = -1.0
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_elevation_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=9.0,
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=7.5,
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 10.1,
            expected_position=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_stop(self):
        """Test the ElevationMotion when moving from position 0 to
        position 10 and then gets stopped.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = 10.0
        velocity = 3.5
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_elevation_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            velocity=velocity,
            expected_duration=expected_duration,
        )
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=3.5,
            expected_motion_state=MotionState.MOVING,
        )
        self.elevation_motion.stop(commanded_tai=_COMMANDED_TAI + 2.0)
        await self.verify_elevation_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=7.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_too_low(self):
        """Test the ElevationMotion when trying to move to a too low
        position.
        """
        initial_position = 10.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = -91.0
        velocity = -3.5
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        try:
            await self.verify_elevation_motion_duration(
                commanded_tai=commanded_tai,
                target_position=target_position,
                velocity=velocity,
                expected_duration=expected_duration,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

    async def test_too_high(self):
        """Test the ElevationMotion when trying to move to a too high
        position.
        """
        initial_position = 10.0
        commanded_tai = _COMMANDED_TAI
        min_position = 0.0
        max_position = 90.0
        max_speed = 3.5
        target_position = 91.0
        velocity = 3.5
        expected_duration = (target_position - initial_position) / velocity
        await self.prepare_elevation_motion(
            initial_position=initial_position,
            min_position=min_position,
            max_position=max_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        try:
            await self.verify_elevation_motion_duration(
                commanded_tai=commanded_tai,
                target_position=target_position,
                velocity=velocity,
                expected_duration=expected_duration,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

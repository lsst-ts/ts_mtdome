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
import math

from lsst.ts.Dome.mock_llc_statuses.mock_motion import AzimuthMotion
from lsst.ts.idl.enums.Dome import MotionState

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

_MAX_SPEED = math.radians(4.0)
_COMMANDED_TAI = 10001.0


class AzimuthMotionTestCase(asynctest.TestCase):
    async def prepare_azimuth_motion(self, initial_position, max_speed, current_tai):
        """Prepare the AzimuthMotion for future commands.

        Parameters
        ----------
        initial_position: `float`
            The initial position.
        max_speed: `float`
            The maximum allowed speed.
        current_tai: `float`
            The current TAI time.
        """
        self.azimuth_motion = AzimuthMotion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=current_tai,
        )

    async def verify_azimuth_motion_duration(
        self, commanded_tai, target_position, crawl_velocity, expected_duration, do_move
    ):
        """Verify that the AzimuthMotion computes the correct
        duration.

        Parameters
        ----------
        commanded_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position.
        crawl_velocity: `float`
            The crawl velocity after the motion.
        expected_duration: `float`
            The expected duration.
        do_move: `bool`
            Move and then crawl (True) or crawl only (False).
        """
        duration = self.azimuth_motion.set_target_position_and_velocity(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            do_move=do_move,
        )
        self.assertEqual(expected_duration, duration)

    async def verify_azimuth_motion_position(
        self, tai, expected_position, expected_motion_state
    ):
        """Verify the position of the AzimuthMotion at the given TAI
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
        position, motion_state = self.azimuth_motion.get_position_and_motion_state(tai)
        self.assertAlmostEqual(expected_position, position)
        self.assertEqual(expected_motion_state, motion_state)

    async def test_move_zero_ten_pos(self):
        """Test the AzimuthMotion when moving from position 0 to
        position 10 degrees and then crawl in positive direction.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (target_position - initial_position) / max_speed
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(8.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=math.radians(10.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 4.0,
            expected_position=math.radians(10.15),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_zero_ten_neg(self):
        """Test the AzimuthMotion when moving from position 0 to
        position 10 degrees and then crawl in negative direction.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(-0.1)
        expected_duration = (target_position - initial_position) / max_speed
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(8.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=math.radians(10.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 4.0,
            expected_position=math.radians(9.85),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_ten_zero_pos(self):
        """Test the AzimuthMotion when moving from position 10 to
        position 0 degrees and then crawl in positive direction.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = 0.0
        crawl_velocity = math.radians(0.1)
        expected_duration = math.fabs((target_position - initial_position) / max_speed)
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(6.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(2.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=math.radians(0.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 4.0,
            expected_position=math.radians(0.15),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_ten_zero_neg(self):
        """Test the AzimuthMotion when moving from position 10 to
        position 0 degrees and then crawl in negative direction.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = 0.0
        crawl_velocity = math.radians(-0.1)
        expected_duration = math.fabs((target_position - initial_position) / max_speed)
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(6.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(2.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.5,
            expected_position=math.radians(0.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 4.0,
            expected_position=math.radians(359.85),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_ten_threefifty_pos(self):
        """Test the AzimuthMotion when moving from position 10 to
        position 350 degrees then crawl in positive direction.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(350.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = math.fabs(
            (target_position - initial_position - 2 * math.pi) / max_speed
        )
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(6.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(2.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(358.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(350.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 6.0,
            expected_position=math.radians(350.1),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_ten_threefifty_neg(self):
        """Test the AzimuthMotion when moving from position 10 to
        position 350 degrees then crawl in negative direction.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(350.0)
        crawl_velocity = math.radians(-0.1)
        expected_duration = math.fabs(
            (target_position - initial_position - 2 * math.pi) / max_speed
        )
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(6.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(2.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(358.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(350.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 6.0,
            expected_position=math.radians(349.9),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_threefifty_ten_pos(self):
        """Test the AzimuthMotion when moving from position 10 to
        position 350 degrees then crawl in positive direction.
        """
        initial_position = math.radians(350.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = math.fabs(
            (target_position - initial_position + 2 * math.pi) / max_speed
        )
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(354.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(358.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(2.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(10.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 6.0,
            expected_position=math.radians(10.1),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_move_threefifty_ten_neg(self):
        """Test the AzimuthMotion when moving from position 10 to
        position 350 degrees then crawl in negative direction.
        """
        initial_position = math.radians(350.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(-0.1)
        expected_duration = math.fabs(
            (target_position - initial_position + 2 * math.pi) / max_speed
        )
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(354.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(358.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(2.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(10.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 6.0,
            expected_position=math.radians(9.9),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_crawl_pos(self):
        """Test the AzimuthMotion when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        initial_position = math.radians(350.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(1.0)
        expected_duration = 0.0
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=False,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(351.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(352.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 10.0,
            expected_position=math.radians(0.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 11.0,
            expected_position=math.radians(1.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 20.0,
            expected_position=math.radians(10.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 21.0,
            expected_position=math.radians(11.0),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_crawl_neg(self):
        """Test the AzimuthMotion when crawling in a positive
        direction while crossing the 0/360 boundary. It should pass the
        target position and keep on crawling
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(350.0)
        crawl_velocity = math.radians(-1.0)
        expected_duration = 0.0
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=False,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(9.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 2.0,
            expected_position=math.radians(8.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 10.0,
            expected_position=math.radians(0.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 11.0,
            expected_position=math.radians(359.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 20.0,
            expected_position=math.radians(350.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 21.0,
            expected_position=math.radians(349.0),
            expected_motion_state=MotionState.CRAWLING,
        )

    async def test_stop_from_moving(self):
        """Test the AzimuthMotion when moving from position 0 to
        position 10 and getting stopped while moving.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = 0
        expected_duration = (target_position - initial_position) / max_speed
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.MOVING,
        )
        self.azimuth_motion.stop(commanded_tai=_COMMANDED_TAI + 2.0)
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(8.0),
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_stop_from_crawling_after_moving(self):
        """Test the AzimuthMotion when moving from position 0 to
        position 10, start crawling and then getting stopped while crawling.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (target_position - initial_position) / max_speed
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(10.05),
            expected_motion_state=MotionState.CRAWLING,
        )
        self.azimuth_motion.stop(commanded_tai=_COMMANDED_TAI + 4.0)
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(10.15),
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_stop_from_crawling(self):
        """Test the AzimuthMotion when crawling and then getting
        stopped.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(1.0)
        expected_duration = 0.0
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=False,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(11.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        self.azimuth_motion.stop(commanded_tai=_COMMANDED_TAI + 4.0)
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(14.0),
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_park_from_moving(self):
        """Test the AzimuthMotion when moving from position 0 to
        position 10 and getting parked while moving.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = 0
        expected_duration = (target_position - initial_position) / max_speed
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.MOVING,
        )
        self.azimuth_motion.park(commanded_tai=_COMMANDED_TAI + 2.0)
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.PARKING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 4.0,
            expected_position=math.radians(0.0),
            expected_motion_state=MotionState.PARKED,
        )

    async def test_park_from_crawling_after_moving(self):
        """Test the AzimuthMotion when moving from position 0 to
        position 10, start crawling and then getting parked while crawling.
        """
        initial_position = 0.0
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(0.1)
        expected_duration = (target_position - initial_position) / max_speed
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=True,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(4.0),
            expected_motion_state=MotionState.MOVING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 3.0,
            expected_position=math.radians(10.05),
            expected_motion_state=MotionState.CRAWLING,
        )
        self.azimuth_motion.park(commanded_tai=_COMMANDED_TAI + 4.0)
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(6.15),
            expected_motion_state=MotionState.PARKING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 6.0,
            expected_position=math.radians(2.15),
            expected_motion_state=MotionState.PARKING,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 7.0,
            expected_position=math.radians(0.0),
            expected_motion_state=MotionState.PARKED,
        )

    async def test_park_from_crawling(self):
        """Test the AzimuthMotion when crawling and then getting
        parked.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(10.0)
        crawl_velocity = math.radians(1.0)
        expected_duration = 0.0
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        await self.verify_azimuth_motion_duration(
            commanded_tai=commanded_tai,
            target_position=target_position,
            crawl_velocity=crawl_velocity,
            expected_duration=expected_duration,
            do_move=False,
        )
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 1.0,
            expected_position=math.radians(11.0),
            expected_motion_state=MotionState.CRAWLING,
        )
        self.azimuth_motion.park(commanded_tai=_COMMANDED_TAI + 4.0)
        await self.verify_azimuth_motion_position(
            tai=_COMMANDED_TAI + 5.0,
            expected_position=math.radians(10.0),
            expected_motion_state=MotionState.PARKING,
        )

    async def test_too_high(self):
        """Test the AzimuthMotion when trying to crawl at a too high
        speed.
        """
        initial_position = math.radians(10.0)
        commanded_tai = _COMMANDED_TAI
        max_speed = _MAX_SPEED
        target_position = math.radians(11.0)
        crawl_velocity = math.radians(5.0)
        expected_duration = 0.0
        await self.prepare_azimuth_motion(
            initial_position=initial_position,
            max_speed=max_speed,
            current_tai=commanded_tai,
        )
        try:
            await self.verify_azimuth_motion_duration(
                commanded_tai=commanded_tai,
                target_position=target_position,
                crawl_velocity=crawl_velocity,
                expected_duration=expected_duration,
                do_move=False,
            )
            self.fail("Expected a ValueError.")
        except ValueError:
            pass

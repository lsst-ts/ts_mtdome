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

import unittest

import pytest
from lsst.ts import mtdome
from lsst.ts.mtdome.mock_llc.mock_motion.shutter_motion import (
    CLOSED_POSITION,
    OPEN_POSITION,
    SHUTTER_SPEED,
)
from lsst.ts.xml.enums.MTDome import MotionState

START_TAI = 10001.0


class ShutterMotionTestCase(unittest.IsolatedAsyncioTestCase):
    async def prepare_shutter_motion(
        self, start_position: float, start_tai: float
    ) -> None:
        """Prepare the ShutterMotion for future commands.

        Parameters
        ----------
        start_position: `float`
            The start position of the azimuth motion.
        start_tai: `float`
            The start TAI time.
        """
        self.shutter_motion = mtdome.mock_llc.ShutterMotion(
            start_position=start_position,
            start_tai=start_tai,
        )

    async def verify_motion_duration(
        self,
        start_tai: float,
        target_position: float,
        expected_duration: float,
        motion_state: MotionState,
    ) -> None:
        """Verify that the ShutterMotion computes the correct
        duration.

        Parameters
        ----------
        start_tai: `float`
            The TAI time at which the command was issued.
        target_position: `float`
            The target position.
        expected_duration: `float`
            The expected duration.
        motion_state: `MotionState`
            The commanded MotionState.
        """
        duration = self.shutter_motion.set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=target_position,
            motion_state=motion_state,
        )
        assert expected_duration == pytest.approx(duration)

    async def verify_motion(
        self,
        tai: float,
        expected_position: float,
        expected_velocity: float,
        expected_motion_state: MotionState,
    ) -> None:
        """Verify the position of the ShutterMotion at the given TAI time.

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
        ) = self.shutter_motion.get_position_velocity_and_motion_state(tai)
        assert expected_position == pytest.approx(position)
        assert expected_velocity == pytest.approx(velocity)
        assert expected_motion_state == motion_state

    async def test_open_shutter(self) -> None:
        """Test opening the shutter from a closed position."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_shutter_motion(
            start_position=start_position, start_tai=start_tai
        )
        await self.verify_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            expected_duration=expected_duration,
            motion_state=MotionState.MOVING,
        )
        for i in range(10):
            await self.verify_motion(
                tai=start_tai + i,
                expected_position=SHUTTER_SPEED * i,
                expected_velocity=SHUTTER_SPEED,
                expected_motion_state=MotionState.MOVING,
            )
        await self.verify_motion(
            tai=start_tai + 10,
            expected_position=OPEN_POSITION,
            expected_velocity=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_close_shutter(self) -> None:
        """Test closing the shutter from a closed position."""
        start_position = OPEN_POSITION
        target_position = CLOSED_POSITION
        start_tai = START_TAI
        expected_duration = -(target_position - start_position) / SHUTTER_SPEED
        await self.prepare_shutter_motion(
            start_position=start_position, start_tai=start_tai
        )
        await self.verify_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            expected_duration=expected_duration,
            motion_state=MotionState.MOVING,
        )
        for i in range(10):
            await self.verify_motion(
                tai=start_tai + i,
                expected_position=OPEN_POSITION - SHUTTER_SPEED * i,
                expected_velocity=-SHUTTER_SPEED,
                expected_motion_state=MotionState.MOVING,
            )
        await self.verify_motion(
            tai=start_tai + 10,
            expected_position=CLOSED_POSITION,
            expected_velocity=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_stop_shutter(self) -> None:
        """Test stopping the shutter while moving."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_shutter_motion(
            start_position=start_position, start_tai=start_tai
        )
        await self.verify_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            expected_duration=expected_duration,
            motion_state=MotionState.MOVING,
        )
        for i in range(6):
            await self.verify_motion(
                tai=start_tai + i,
                expected_position=SHUTTER_SPEED * i,
                expected_velocity=SHUTTER_SPEED,
                expected_motion_state=MotionState.MOVING,
            )
        self.shutter_motion.stop(start_tai=start_tai + 7)
        await self.verify_motion(
            tai=start_tai + 7.1,
            expected_position=70.0,
            expected_velocity=0.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_go_stationary_shutter(self) -> None:
        """Test setting the shutter to GO_STATIONARY while moving."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_shutter_motion(
            start_position=start_position, start_tai=start_tai
        )
        await self.verify_motion_duration(
            start_tai=start_tai,
            target_position=target_position,
            expected_duration=expected_duration,
            motion_state=MotionState.MOVING,
        )
        for i in range(6):
            await self.verify_motion(
                tai=start_tai + i,
                expected_position=SHUTTER_SPEED * i,
                expected_velocity=SHUTTER_SPEED,
                expected_motion_state=MotionState.MOVING,
            )
        self.shutter_motion.go_stationary(start_tai=start_tai + 7)
        await self.verify_motion(
            tai=start_tai + 7.1,
            expected_position=70.0,
            expected_velocity=0.0,
            expected_motion_state=mtdome.InternalMotionState.STATIONARY,
        )

    async def test_exit_fault(self) -> None:
        """Test going to and exiting from ERROR state while moving."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_shutter_motion(
            start_position=start_position, start_tai=START_TAI
        )
        await self.verify_motion_duration(
            start_tai=START_TAI,
            target_position=target_position,
            expected_duration=expected_duration,
            motion_state=MotionState.MOVING,
        )
        await self.verify_motion(
            tai=START_TAI + 1.0,
            expected_position=10.0,
            expected_velocity=SHUTTER_SPEED,
            expected_motion_state=MotionState.MOVING,
        )

        # This sets the status of the state machine to ERROR.
        drives_in_error = [0, 1]
        expected_drive_error_state = [False, True]
        current_tai = START_TAI + 1.1
        self.shutter_motion.set_fault(current_tai, drives_in_error)
        assert self.shutter_motion.drives_in_error_state == expected_drive_error_state
        await self.verify_motion(
            tai=current_tai,
            expected_position=11.0,
            expected_velocity=0.0,
            expected_motion_state=MotionState.ERROR,
        )

        current_tai = START_TAI + 2.0

        # Now call exit_fault. This will fail because there still are drives at
        # fault.
        with pytest.raises(RuntimeError):
            self.shutter_motion.exit_fault(current_tai)

        # Reset the drives.
        expected_drive_error_state = [False, False]
        reset = [0, 1]
        self.shutter_motion.reset_drives(current_tai, reset)
        assert self.shutter_motion.drives_in_error_state == expected_drive_error_state

        # Now call exit_fault which will not fail because the drives have been
        # reset.
        self.shutter_motion.exit_fault(current_tai)
        await self.verify_motion(
            tai=current_tai,
            expected_position=11.0,
            expected_velocity=0.0,
            expected_motion_state=mtdome.InternalMotionState.STATIONARY,
        )
        assert self.shutter_motion.drives_in_error_state == expected_drive_error_state
        assert self.shutter_motion.motion_state_in_error is False

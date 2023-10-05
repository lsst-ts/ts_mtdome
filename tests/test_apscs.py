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
from lsst.ts.mtdome.mock_llc.apscs import CURRENT_PER_MOTOR, NUM_SHUTTERS
from lsst.ts.mtdome.mock_llc.mock_motion.shutter_motion import (
    CLOSED_POSITION,
    NUM_MOTORS_PER_SHUTTER,
    OPEN_POSITION,
    SHUTTER_SPEED,
)
from lsst.ts.mtdome.power_management.power_draw_constants import APS_POWER_DRAW
from lsst.ts.xml.enums.MTDome import MotionState

START_TAI = 10001.0


class ApscsTestCase(unittest.IsolatedAsyncioTestCase):
    async def prepare_apscs(self, start_position: float, start_tai: float) -> None:
        """Prepare the ApSCS for future commands.

        Parameters
        ----------
        start_position: `float`
            The start position of the azimuth motion.
        start_tai: `float`
            The start TAI time.
        """
        self.apscs = mtdome.mock_llc.ApscsStatus(start_tai=start_tai)
        shutter_motion = [
            mtdome.mock_llc.ShutterMotion(
                start_position=start_position, start_tai=start_tai
            ),
            mtdome.mock_llc.ShutterMotion(
                start_position=start_position, start_tai=start_tai
            ),
        ]
        self.apscs.shutter_motion = shutter_motion

    async def verify_apscs(
        self,
        tai: float,
        expected_position: float,
        expected_motion_state: MotionState,
    ) -> None:
        """Verify the position of the ApSCS at the given TAI time.

        Parameters
        ----------
        tai: `float`
            The TAI time to compute the position for.
        expected_position: `float`
            The expected position at the given TAI time.
        expected_motion_state: `float`
            The expected motion state at the given TAI time.
        """
        await self.apscs.determine_status(current_tai=tai)
        assert [expected_position] * NUM_SHUTTERS == pytest.approx(
            self.apscs.llc_status["positionActual"]
        )
        assert [expected_motion_state.name] * NUM_SHUTTERS == self.apscs.llc_status[
            "status"
        ]["status"]
        expected_drive_current: list[float] = (
            [0.0] * NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER
        )
        expected_power_draw = 0.0
        if expected_motion_state in [
            MotionState.CRAWLING,
            MotionState.MOVING,
        ]:
            expected_drive_current = (
                [CURRENT_PER_MOTOR] * NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER
            )
            expected_power_draw = APS_POWER_DRAW
        assert expected_drive_current == self.apscs.llc_status["driveCurrentActual"]
        assert expected_power_draw == self.apscs.llc_status["powerDraw"]

    async def test_open_shutter(self) -> None:
        """Test opening the shutter from a closed position."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_apscs(start_position=start_position, start_tai=start_tai)
        duration = await self.apscs.openShutter(start_tai=start_tai)
        assert expected_duration == duration
        for i in range(10):
            await self.verify_apscs(
                tai=start_tai + i,
                expected_position=SHUTTER_SPEED * i,
                expected_motion_state=MotionState.MOVING,
            )
        await self.verify_apscs(
            tai=start_tai + 10,
            expected_position=OPEN_POSITION,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_close_shutter(self) -> None:
        """Test closing the shutter from a closed position."""
        start_position = OPEN_POSITION
        target_position = CLOSED_POSITION
        start_tai = START_TAI
        expected_duration = -(target_position - start_position) / SHUTTER_SPEED
        await self.prepare_apscs(start_position=start_position, start_tai=start_tai)
        duration = await self.apscs.closeShutter(start_tai=start_tai)
        assert expected_duration == duration
        for i in range(10):
            await self.verify_apscs(
                tai=start_tai + i,
                expected_position=OPEN_POSITION - SHUTTER_SPEED * i,
                expected_motion_state=MotionState.MOVING,
            )
        await self.verify_apscs(
            tai=start_tai + 10,
            expected_position=CLOSED_POSITION,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_stop_shutter(self) -> None:
        """Test stopping the shutter while moving."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_apscs(start_position=start_position, start_tai=start_tai)
        duration = await self.apscs.openShutter(start_tai=start_tai)
        assert expected_duration == duration
        for i in range(6):
            await self.verify_apscs(
                tai=start_tai + i,
                expected_position=SHUTTER_SPEED * i,
                expected_motion_state=MotionState.MOVING,
            )
        await self.apscs.stopShutter(start_tai=start_tai + 7)
        await self.verify_apscs(
            tai=start_tai + 7.1,
            expected_position=70.0,
            expected_motion_state=MotionState.STOPPED,
        )

    async def test_go_stationary_shutter(self) -> None:
        """Test setting the shutter to GO_STATIONARY while moving."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_apscs(start_position=start_position, start_tai=start_tai)
        duration = await self.apscs.openShutter(start_tai=start_tai)
        assert expected_duration == duration
        for i in range(6):
            await self.verify_apscs(
                tai=start_tai + i,
                expected_position=SHUTTER_SPEED * i,
                expected_motion_state=MotionState.MOVING,
            )
        await self.apscs.go_stationary(start_tai=start_tai + 7)
        await self.verify_apscs(
            tai=start_tai + 7.1,
            expected_position=70.0,
            expected_motion_state=mtdome.InternalMotionState.STATIONARY,
        )

    async def test_exit_fault(self) -> None:
        """Test going to and exiting from ERROR state while moving."""
        start_position = CLOSED_POSITION
        target_position = OPEN_POSITION
        start_tai = START_TAI
        expected_duration = (target_position - start_position) / SHUTTER_SPEED
        await self.prepare_apscs(start_position=start_position, start_tai=start_tai)
        duration = await self.apscs.openShutter(start_tai=start_tai)
        assert expected_duration == duration
        await self.verify_apscs(
            tai=START_TAI + 1.0,
            expected_position=10.0,
            expected_motion_state=MotionState.MOVING,
        )

        # This sets the status of the state machine to ERROR.
        drives_in_error = [0, 1, 0, 1]
        expected_drive_error_state = [False, True]
        current_tai = START_TAI + 1.1
        await self.apscs.set_fault(current_tai, drives_in_error)
        for i in range(NUM_SHUTTERS):
            assert (
                self.apscs.shutter_motion[i].drives_in_error_state
                == expected_drive_error_state
            )
        await self.verify_apscs(
            tai=current_tai,
            expected_position=11.0,
            expected_motion_state=MotionState.ERROR,
        )

        current_tai = START_TAI + 2.0

        # Now call exit_fault. This will fail because there still are drives at
        # fault.
        with pytest.raises(RuntimeError):
            await self.apscs.exit_fault(current_tai)

        # Reset the drives.
        expected_drive_error_state = [False, False]
        reset = [0, 1, 0, 1]
        await self.apscs.reset_drives_shutter(current_tai, reset)
        for i in range(NUM_SHUTTERS):
            assert (
                self.apscs.shutter_motion[i].drives_in_error_state
                == expected_drive_error_state
            )

        # Now call exit_fault which will not fail because the drives have been
        # reset.
        await self.apscs.exit_fault(current_tai)
        await self.verify_apscs(
            tai=current_tai,
            expected_position=11.0,
            expected_motion_state=mtdome.InternalMotionState.STATIONARY,
        )
        for i in range(NUM_SHUTTERS):
            assert (
                self.apscs.shutter_motion[i].drives_in_error_state
                == expected_drive_error_state
            )
        # assert self.apscs.motion_state_in_error is False

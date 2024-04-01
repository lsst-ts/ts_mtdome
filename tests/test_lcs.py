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

import typing
import unittest

import numpy as np
import pytest
from lsst.ts import mtdome
from lsst.ts.mtdome.mock_llc.lcs import (
    CURRENT_PER_MOTOR,
    NUM_LOUVERS,
    NUM_MOTORS_PER_LOUVER,
)
from lsst.ts.mtdome.power_management.power_draw_constants import LOUVERS_POWER_DRAW
from lsst.ts.xml.enums.MTDome import MotionState

START_TAI = 10001.0


class LcsTestCase(unittest.IsolatedAsyncioTestCase):
    """A simple test class for testing some of the basic LCS commands."""

    async def verify_lcs(self, expected_positions: dict[int, float]) -> None:
        """Utility method for verifying the positions of the louvers against
        the provided IDs and target positions.

        Parameters
        ----------
        expected_positions : `dict`[`int`, `float`]
            A dict with the target positions for the IDS of the louvers to move
            to.

        Notes
        -----
        For each louver that will be moved, both an ID and a target position
        needs to be given. It is assumed that the indices of the IDs and the
        target positions are lined up.
        """
        await self.lcs.determine_status(current_tai=0.0)
        lcs_status = self.lcs.llc_status
        await self.verify_state(lcs_status, expected_positions, current_tai=0.0)
        for louver_id, position_actual in enumerate(lcs_status["positionActual"]):
            if louver_id in expected_positions:
                assert expected_positions[louver_id] == position_actual
            else:
                assert 0 == position_actual
        for louver_id, position_commanded in enumerate(lcs_status["positionCommanded"]):
            if louver_id in expected_positions:
                assert expected_positions[louver_id] == position_commanded
            else:
                assert 0 == position_commanded
        for louver_id in range(NUM_LOUVERS):
            drive_current_actual_motor1 = lcs_status["driveCurrentActual"][
                louver_id * NUM_MOTORS_PER_LOUVER
            ]
            drive_current_actual_motor2 = lcs_status["driveCurrentActual"][
                louver_id * NUM_MOTORS_PER_LOUVER + 1
            ]
            if louver_id in expected_positions:
                if lcs_status["status"]["status"][louver_id] == MotionState.MOVING:
                    assert drive_current_actual_motor1 == CURRENT_PER_MOTOR
                    assert drive_current_actual_motor2 == CURRENT_PER_MOTOR
                    assert lcs_status["powerDraw"] == LOUVERS_POWER_DRAW
            else:
                assert drive_current_actual_motor1 == pytest.approx(0.0)
                assert drive_current_actual_motor2 == pytest.approx(0.0)
                assert lcs_status["powerDraw"] == pytest.approx(0.0)

    async def verify_state(
        self,
        lcs_status: dict[str, typing.Any],
        expected_positions: dict[int, float],
        current_tai: float,
    ) -> None:
        for louver_id, status in enumerate(lcs_status["status"]["status"]):
            if louver_id in expected_positions:
                if expected_positions[louver_id] > 0:
                    if current_tai == START_TAI:
                        assert MotionState.MOVING.name == status
                else:
                    assert MotionState.STOPPED.name == status
            else:
                assert mtdome.InternalMotionState.STATIONARY.name == status

    async def test_set_louvers(self) -> None:
        """Test setting the louvers to the indicated position."""
        # A dict of louver ID (int) and expected position (float).
        expected_positions = {
            5: 100.0,
            6: 80.0,
            7: 70.0,
            8: 85.0,
            9: 25.0,
            10: 60.0,
        }
        self.lcs = mtdome.mock_llc.LcsStatus()
        position = np.full(NUM_LOUVERS, -1.0, dtype=float)
        for louver_id in expected_positions:
            position[louver_id] = expected_positions[louver_id]
        await self.lcs.setLouvers(position=position, current_tai=START_TAI)
        for louver_id in expected_positions:
            self.lcs.current_state[louver_id] = MotionState.MOVING.name
            await self.lcs.evaluate_state(
                current_tai=START_TAI + 31.0, louver_id=louver_id
            )
        await self.verify_lcs(expected_positions=expected_positions)

    async def test_close_louvers(self) -> None:
        """Test closing the louvers from an open position."""
        # A dict of louver ID (int) and expected position (float).
        expected_positions = {
            5: 100.0,
            6: 80.0,
            7: 70.0,
            8: 85.0,
            9: 25.0,
            10: 60.0,
        }
        self.lcs = mtdome.mock_llc.LcsStatus()
        for louver_id in expected_positions:
            self.lcs.position_actual[louver_id] = expected_positions[louver_id]
            self.lcs.start_position[louver_id] = 100.0

        # Now close the louvers.
        await self.lcs.closeLouvers(current_tai=START_TAI)
        for louver_id in expected_positions:
            self.lcs.current_state[louver_id] = MotionState.MOVING.name
            await self.lcs.evaluate_state(
                current_tai=START_TAI + 31.0, louver_id=louver_id
            )
        expected_positions = {
            5: 0.0,
            6: 0.0,
            7: 0.0,
            8: 0.0,
            9: 0.0,
            10: 0.0,
        }
        await self.verify_lcs(expected_positions=expected_positions)

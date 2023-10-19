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

import numpy as np
from lsst.ts import mtdome
from lsst.ts.mtdome.mock_llc.lcs import (
    CURRENT_PER_MOTOR,
    NUM_LOUVERS,
    NUM_MOTORS_PER_LOUVER,
)
from lsst.ts.mtdome.power_draw_constants import LOUVERS_POWER_DRAW
from lsst.ts.xml.enums.MTDome import MotionState

START_TAI = 10001.0


class LcsTestCase(unittest.IsolatedAsyncioTestCase):
    """A simple test class for testing some of the basic LCS commands. More
    will be added as soon as the state machine for the LCS has been defined.
    """

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
        for index, status in enumerate(lcs_status["status"]["status"]):
            if index in expected_positions:
                if expected_positions[index] > 0:
                    assert MotionState.OPEN.name == status
                else:
                    assert MotionState.CLOSED.name == status
            else:
                assert MotionState.CLOSED.name == status
        for index, positionActual in enumerate(lcs_status["positionActual"]):
            if index in expected_positions:
                assert expected_positions[index] == positionActual
            else:
                assert 0 == positionActual
        for index, positionCommanded in enumerate(lcs_status["positionCommanded"]):
            if index in expected_positions:
                assert expected_positions[index] == positionCommanded
            else:
                assert 0 == positionCommanded
        for index in range(NUM_LOUVERS):
            driveCurrentActualMotor1 = lcs_status["driveCurrentActual"][
                index * NUM_MOTORS_PER_LOUVER
            ]
            driveCurrentActualMotor2 = lcs_status["driveCurrentActual"][
                index * NUM_MOTORS_PER_LOUVER + 1
            ]
            if index in expected_positions:
                if lcs_status["status"]["status"][index] == MotionState.MOVING:
                    assert driveCurrentActualMotor1 == CURRENT_PER_MOTOR
                    assert driveCurrentActualMotor2 == CURRENT_PER_MOTOR
                    assert lcs_status["powerDraw"] == LOUVERS_POWER_DRAW
            else:
                assert driveCurrentActualMotor1 == 0.0
                assert driveCurrentActualMotor2 == 0.0
                assert lcs_status["powerDraw"] == 0.0

    async def test_set_louvers(self) -> None:
        """Test setting the louvers from to the indicated position."""
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
        await self.lcs.setLouvers(position=position)
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
        position = np.full(NUM_LOUVERS, -1.0, dtype=float)
        for louver_id in expected_positions:
            position[louver_id] = expected_positions[louver_id]
        await self.lcs.setLouvers(position=position)

        # Now close the louvers.
        await self.lcs.closeLouvers()
        expected_positions = {
            5: 0.0,
            6: 0.0,
            7: 0.0,
            8: 0.0,
            9: 0.0,
            10: 0.0,
        }
        await self.verify_lcs(expected_positions=expected_positions)

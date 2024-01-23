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

from lsst.ts import mtdome
from lsst.ts.xml.enums.MTDome import MotionState

START_TAI = 10001.0


class ThcsTestCase(unittest.IsolatedAsyncioTestCase):
    """A simple test class for testing some of the basic ThCS commands."""

    async def test_start_and_stop_cooling(self) -> None:
        thcs = mtdome.mock_llc.ThcsStatus()
        assert thcs.current_state == MotionState.DISABLED
        assert thcs.target_state == MotionState.DISABLED

        await thcs.start_cooling(current_tai=START_TAI)
        assert thcs.current_state == MotionState.DISABLED
        assert thcs.target_state == MotionState.ENABLED

        await thcs.evaluate_state()
        assert thcs.current_state == MotionState.ENABLING
        assert thcs.target_state == MotionState.ENABLED

        await thcs.evaluate_state()
        assert thcs.current_state == MotionState.ENABLED
        assert thcs.target_state == MotionState.ENABLED

        await thcs.stop_cooling(current_tai=START_TAI)
        assert thcs.current_state == MotionState.ENABLED
        assert thcs.target_state == MotionState.DISABLED

        await thcs.evaluate_state()
        assert thcs.current_state == MotionState.DISABLING
        assert thcs.target_state == MotionState.DISABLED

        await thcs.evaluate_state()
        assert thcs.current_state == MotionState.DISABLED
        assert thcs.target_state == MotionState.DISABLED

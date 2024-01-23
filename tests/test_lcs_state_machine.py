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
from lsst.ts.xml.enums.MTDome import MotionState


class LcsStateMachineTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_handle_moving_open(self) -> None:
        index = 0
        lcs = mtdome.mock_llc.LcsStatus()
        lcs.current_state[index] = MotionState.MOVING.name
        lcs.target_state[index] = MotionState.OPEN.name
        lcs.position_commanded[index] = 100

        for i in range(30):
            lcs.current_tai = i
            await lcs.handle_moving(index)
            assert lcs.current_state[index] == MotionState.MOVING.name
            assert lcs.position_actual[index] != lcs.position_commanded[index]

        lcs.current_tai = 31
        await lcs.handle_moving(index)
        assert lcs.current_state[index] == MotionState.STOPPING.name
        assert lcs.position_actual[index] == pytest.approx(
            lcs.position_commanded[index]
        )

    async def test_handle_moving_close(self) -> None:
        index = 0
        lcs = mtdome.mock_llc.LcsStatus()
        lcs.current_state[index] = MotionState.MOVING.name
        lcs.target_state[index] = MotionState.CLOSED.name
        lcs.position_actual[index] = 100
        lcs.start_position[index] = 100
        lcs.position_commanded[index] = 0
        for i in range(30):
            lcs.current_tai = i
            await lcs.handle_moving(index)
            assert lcs.current_state[index] == MotionState.MOVING.name
            assert lcs.position_actual[index] != lcs.position_commanded[index]

        lcs.current_tai = 31
        await lcs.handle_moving(index)
        assert lcs.current_state[index] == MotionState.STOPPING.name
        assert lcs.position_actual[index] == pytest.approx(
            lcs.position_commanded[index]
        )

    async def test_full_state_cycle(self) -> None:
        index = 0
        lcs = mtdome.mock_llc.LcsStatus()
        await lcs.evaluate_state(current_tai=30.0)
        assert lcs.current_state[index] == mtdome.InternalMotionState.STATIONARY.name

        lcs.target_state[index] = MotionState.OPEN.name
        lcs.position_commanded[index] = 100
        state: MotionState | mtdome.InternalMotionState
        i = 0.0
        for state in [
            MotionState.ENABLING_MOTOR_POWER.name,
            MotionState.MOTOR_POWER_ON.name,
            MotionState.GO_NORMAL.name,
            MotionState.DISENGAGING_BRAKES.name,
            MotionState.BRAKES_DISENGAGED.name,
            MotionState.MOVING.name,
            MotionState.STOPPING.name,
            MotionState.STOPPED.name,
        ]:
            i = i + 0.01
            await lcs.evaluate_state(current_tai=30.0 + i)
            assert lcs.current_state[index] == state

        # Repeat the check a few times to ensure that the state remains the
        # same.
        for c in range(3):
            await lcs.evaluate_state(current_tai=30.0 + c * 0.01)
            assert lcs.start_state[index] == MotionState.OPEN.name
            assert lcs.current_state[index] == MotionState.STOPPED.name

        lcs.target_state[index] = MotionState.CLOSED.name
        lcs.position_commanded[index] = 0
        for state in [
            MotionState.MOVING.name,
            MotionState.STOPPING.name,
            MotionState.STOPPED.name,
        ]:
            await lcs.evaluate_state(current_tai=60)
            assert lcs.current_state[index] == state

        lcs.target_state[index] = mtdome.InternalMotionState.STATIONARY.name
        i = 0.0
        for state in [
            MotionState.ENGAGING_BRAKES.name,
            MotionState.BRAKES_ENGAGED.name,
            MotionState.GO_STATIONARY.name,
            MotionState.DISABLING_MOTOR_POWER.name,
            MotionState.MOTOR_POWER_OFF.name,
            mtdome.InternalMotionState.STATIONARY.name,
        ]:
            i = i + 0.01
            await lcs.evaluate_state(60.0 + i)
            assert lcs.current_state[index] == state

        # Repeat the check a few times to ensure that the state remains the
        # same.
        for c in range(3):
            await lcs.evaluate_state(current_tai=61.0 + c * 0.01)
            assert (
                lcs.current_state[index] == mtdome.InternalMotionState.STATIONARY.name
            )
            assert lcs.start_state[index] == mtdome.InternalMotionState.STATIONARY.name

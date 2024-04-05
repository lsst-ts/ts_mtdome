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
        louver_id = 0
        lcs = mtdome.mock_llc.LcsStatus()
        lcs.current_state[louver_id] = MotionState.MOVING.name
        lcs.target_state[louver_id] = mtdome.InternalMotionState.STATIONARY.name
        lcs.position_commanded[louver_id] = 100

        for i in range(30):
            current_tai = i
            await lcs.evaluate_state(current_tai, louver_id)
            assert lcs.current_state[louver_id] == MotionState.MOVING.name
            assert lcs.position_actual[louver_id] != lcs.position_commanded[louver_id]

        current_tai = 31
        await lcs.evaluate_state(current_tai, louver_id)
        assert lcs.current_state[louver_id] == MotionState.STOPPING.name
        assert lcs.position_actual[louver_id] == pytest.approx(
            lcs.position_commanded[louver_id]
        )

    async def test_handle_moving_close(self) -> None:
        louver_id = 0
        lcs = mtdome.mock_llc.LcsStatus()
        lcs.current_state[louver_id] = MotionState.MOVING.name
        lcs.target_state[louver_id] = mtdome.InternalMotionState.STATIONARY.name
        lcs.position_actual[louver_id] = 100
        lcs.start_position[louver_id] = 100
        lcs.position_commanded[louver_id] = 0
        for i in range(30):
            current_tai = i
            await lcs.evaluate_state(current_tai, louver_id)
            assert lcs.current_state[louver_id] == MotionState.MOVING.name
            assert lcs.position_actual[louver_id] != lcs.position_commanded[louver_id]

        current_tai = 31
        await lcs.evaluate_state(current_tai, louver_id)
        assert lcs.current_state[louver_id] == MotionState.STOPPING.name
        assert lcs.position_actual[louver_id] == pytest.approx(
            lcs.position_commanded[louver_id]
        )

    async def test_full_state_cycle(self) -> None:
        louver_id = 0
        lcs = mtdome.mock_llc.LcsStatus()
        await lcs.evaluate_state(current_tai=30.0, louver_id=louver_id)
        assert (
            lcs.current_state[louver_id] == mtdome.InternalMotionState.STATIONARY.name
        )

        lcs.start_state[louver_id] = MotionState.OPENING.name
        lcs.target_state[louver_id] = mtdome.InternalMotionState.STATIONARY.name
        lcs.position_commanded[louver_id] = 100
        state: MotionState | mtdome.InternalMotionState
        for state in [
            MotionState.ENABLING_MOTOR_POWER.name,
            MotionState.MOTOR_POWER_ON.name,
            MotionState.GO_NORMAL.name,
            MotionState.DISENGAGING_BRAKES.name,
            MotionState.BRAKES_DISENGAGED.name,
            MotionState.MOVING.name,
            MotionState.STOPPING.name,
            MotionState.STOPPED.name,
            MotionState.ENGAGING_BRAKES.name,
            MotionState.BRAKES_ENGAGED.name,
            MotionState.GO_STATIONARY.name,
            MotionState.DISABLING_MOTOR_POWER.name,
            MotionState.MOTOR_POWER_OFF.name,
        ]:
            await lcs.evaluate_state(current_tai=30.0, louver_id=louver_id)
            assert lcs.current_state[louver_id] == state
            assert lcs.start_state[louver_id] == MotionState.OPENING.name

        # Repeat the check a few times to ensure that the state remains the
        # same.
        for _ in range(3):
            await lcs.evaluate_state(current_tai=30.0, louver_id=louver_id)
            assert (
                lcs.start_state[louver_id] == mtdome.InternalMotionState.STATIONARY.name
            )
            assert (
                lcs.current_state[louver_id]
                == mtdome.InternalMotionState.STATIONARY.name
            )

        lcs.start_state[louver_id] = MotionState.CLOSING.name
        lcs.target_state[louver_id] = mtdome.InternalMotionState.STATIONARY.name
        lcs.position_commanded[louver_id] = 0
        for state in [
            MotionState.ENABLING_MOTOR_POWER.name,
            MotionState.MOTOR_POWER_ON.name,
            MotionState.GO_NORMAL.name,
            MotionState.DISENGAGING_BRAKES.name,
            MotionState.BRAKES_DISENGAGED.name,
            MotionState.MOVING.name,
            MotionState.STOPPING.name,
            MotionState.STOPPED.name,
            MotionState.ENGAGING_BRAKES.name,
            MotionState.BRAKES_ENGAGED.name,
            MotionState.GO_STATIONARY.name,
            MotionState.DISABLING_MOTOR_POWER.name,
            MotionState.MOTOR_POWER_OFF.name,
        ]:
            await lcs.evaluate_state(current_tai=60.0, louver_id=louver_id)
            assert lcs.current_state[louver_id] == state

        # Repeat the check a few times to ensure that the state remains the
        # same.
        for _ in range(3):
            await lcs.evaluate_state(current_tai=60.0, louver_id=louver_id)
            assert (
                lcs.current_state[louver_id]
                == mtdome.InternalMotionState.STATIONARY.name
            )
            assert (
                lcs.start_state[louver_id] == mtdome.InternalMotionState.STATIONARY.name
            )

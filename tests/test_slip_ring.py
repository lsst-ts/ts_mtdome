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

import logging
import unittest
from unittest import mock

import pytest
from lsst.ts import mtdome
from utils_for_tests import CoolDownTestData, SlipRingTestData


class SlipRingTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_get_cool_down_time(self) -> None:
        self.log = logging.getLogger(type(self).__name__)
        slip_ring = mtdome.power_management.SlipRing(log=self.log, index=1)

        data = [
            SlipRingTestData(
                max_power_drawn=0.0, time_over_limit=0.0, expected_cool_down_time=0.0
            ),
            SlipRingTestData(
                max_power_drawn=mtdome.power_management.CONTINUOUS_SLIP_RING_POWER_CAPACITY,
                time_over_limit=0.0,
                expected_cool_down_time=0.0,
            ),
            SlipRingTestData(
                max_power_drawn=mtdome.power_management.CONTINUOUS_SLIP_RING_POWER_CAPACITY
                + 10000.0,
                time_over_limit=100.0,
                expected_cool_down_time=30.303030303030,
            ),
            SlipRingTestData(
                max_power_drawn=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                time_over_limit=mtdome.power_management.MAXIMUM_OVER_LOW_LIMIT_TIME,
                expected_cool_down_time=mtdome.power_management.MAXIMUM_COOL_DOWN_TIME,
            ),
        ]

        for d in data:
            slip_ring.max_power_drawn = d.max_power_drawn
            slip_ring.time_over_limit = d.time_over_limit
            assert slip_ring.get_cool_down_time() == pytest.approx(
                d.expected_cool_down_time
            )

    async def test_get_available_power(self) -> None:
        self.log = logging.getLogger(type(self).__name__)
        slip_ring = mtdome.power_management.SlipRing(
            log=self.log, index=1, disabled=True
        )
        assert slip_ring.get_available_power(0.0) == pytest.approx(0.0)

        with mock.patch(
            "lsst.ts.mtdome.power_management.slip_ring.utils.current_tai"
        ) as mock_tai:
            slip_ring = mtdome.power_management.SlipRing(log=self.log, index=1)
            assert slip_ring.get_available_power(0.0) == pytest.approx(
                mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY
            )
            assert slip_ring.state == mtdome.SlipRingState.BELOW_LOW_LIMIT
            mock_tai.assert_not_called()

            # Case where the power isn't over the limit for too long.
            for test_data in [
                CoolDownTestData(
                    tai=1.0,
                    power_drawn=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                    expected_power_available=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                    expected_state=mtdome.SlipRingState.OVER_LOW_LIMIT,
                ),
                CoolDownTestData(
                    tai=100.0,
                    power_drawn=0.0,
                    expected_power_available=0.0,
                    expected_state=mtdome.SlipRingState.COOLING_DOWN,
                ),
                CoolDownTestData(
                    tai=100.1,
                    power_drawn=0.0,
                    expected_power_available=0.0,
                    expected_state=mtdome.SlipRingState.COOLING_DOWN,
                ),
                CoolDownTestData(
                    tai=166.0,
                    power_drawn=0.0,
                    expected_power_available=0.0,
                    expected_state=mtdome.SlipRingState.COOLING_DOWN,
                ),
                CoolDownTestData(
                    tai=166.1,
                    power_drawn=0.0,
                    expected_power_available=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                    expected_state=mtdome.SlipRingState.BELOW_LOW_LIMIT,
                ),
            ]:
                mock_tai.return_value = test_data.tai
                assert slip_ring.get_available_power(
                    test_data.power_drawn
                ) == pytest.approx(test_data.expected_power_available)
                assert slip_ring.state == test_data.expected_state
                mock_tai.assert_called()

            # Case where the power is over the limit for too long.
            for test_data in [
                CoolDownTestData(
                    tai=1.0,
                    power_drawn=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                    expected_power_available=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                    expected_state=mtdome.SlipRingState.OVER_LOW_LIMIT,
                ),
                CoolDownTestData(
                    tai=mtdome.power_management.MAXIMUM_OVER_LOW_LIMIT_TIME + 2.0,
                    power_drawn=0.0,
                    expected_power_available=0.0,
                    expected_state=mtdome.SlipRingState.COOLING_DOWN,
                ),
                CoolDownTestData(
                    tai=mtdome.power_management.MAXIMUM_OVER_LOW_LIMIT_TIME
                    + mtdome.power_management.MAXIMUM_COOL_DOWN_TIME,
                    power_drawn=0.0,
                    expected_power_available=0.0,
                    expected_state=mtdome.SlipRingState.COOLING_DOWN,
                ),
                CoolDownTestData(
                    tai=mtdome.power_management.MAXIMUM_OVER_LOW_LIMIT_TIME
                    + mtdome.power_management.MAXIMUM_COOL_DOWN_TIME
                    + 2.6,
                    power_drawn=0.0,
                    expected_power_available=0.0,
                    expected_state=mtdome.SlipRingState.COOLING_DOWN,
                ),
                CoolDownTestData(
                    tai=mtdome.power_management.MAXIMUM_OVER_LOW_LIMIT_TIME
                    + mtdome.power_management.MAXIMUM_COOL_DOWN_TIME
                    + 2.7,
                    power_drawn=0.0,
                    expected_power_available=mtdome.power_management.MAXIMUM_SLIP_RING_POWER_CAPACITY,
                    expected_state=mtdome.SlipRingState.BELOW_LOW_LIMIT,
                ),
            ]:
                mock_tai.return_value = test_data.tai
                assert slip_ring.get_available_power(
                    test_data.power_drawn
                ) == pytest.approx(test_data.expected_power_available)
                assert slip_ring.state == test_data.expected_state
                mock_tai.assert_called()

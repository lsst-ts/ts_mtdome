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

__all__ = ["CbcsStatus", "NUM_CAPACITOR_BANKS"]

import logging

import numpy as np

from .base_mock_llc import DEFAULT_MESSAGES, BaseMockStatus

NUM_CAPACITOR_BANKS = 2


class CbcsStatus(BaseMockStatus):
    """Represents the status of the Capacitor Banks in simulation mode."""

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("MockCbcsStatus")

        # Variables holding the status of the mock Capacitor Banks.
        self.messages = DEFAULT_MESSAGES
        self.fuse_intervention = np.zeros(NUM_CAPACITOR_BANKS, dtype=float)
        self.smoke_detected = np.full(NUM_CAPACITOR_BANKS, False, dtype=bool)
        self.high_temperature = np.full(NUM_CAPACITOR_BANKS, False, dtype=bool)
        self.low_residual_voltage = np.full(NUM_CAPACITOR_BANKS, False, dtype=bool)
        self.door_open = np.full(NUM_CAPACITOR_BANKS, False, dtype=bool)

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """
        time_diff = current_tai - self.command_time_tai
        self.log.debug(
            f"current_tai = {current_tai}, self.command_time_tai = {self.command_time_tai}, "
            f"time_diff = {time_diff}"
        )
        self.llc_status = {
            "status": {
                "messages": self.messages,
            },
            "fuseIntervention": self.fuse_intervention.tolist(),
            "smokeDetected": self.smoke_detected.tolist(),
            "highTemperature": self.high_temperature.tolist(),
            "lowResidualVoltage": self.low_residual_voltage.tolist(),
            "doorOpen": self.door_open.tolist(),
            "timestampUTC": current_tai,
        }
        self.log.debug(f"cbcs_state = {self.llc_status}")

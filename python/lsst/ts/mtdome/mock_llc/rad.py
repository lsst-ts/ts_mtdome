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

__all__ = ["RadStatus", "NUM_DOORS", "NUM_LIMIT_SWITCHES", "NUM_LOCKING_PINS"]

import logging

import numpy as np
from lsst.ts.xml.enums.MTDome import MotionState, RadLockingPinState

from .base_mock_llc import DEFAULT_MESSAGES, BaseMockStatus

NUM_DOORS = 2
NUM_LIMIT_SWITCHES = 4
NUM_LOCKING_PINS = 2


class RadStatus(BaseMockStatus):
    """Represents the status of the Rear Access Door in simulation mode."""

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("MockRadStatus")

        # Variables holding the status of the mock Rear Access Door.
        self.status = np.full(NUM_DOORS, MotionState.CLOSED.name, dtype=object)
        self.messages = DEFAULT_MESSAGES
        self.position_actual = np.zeros(NUM_DOORS, dtype=float)
        self.position_commanded = np.zeros(NUM_DOORS, dtype=float)
        self.drive_torque_actual = np.zeros(NUM_DOORS, dtype=float)
        self.drive_torque_commanded = np.zeros(NUM_DOORS, dtype=float)
        self.drive_current_actual = np.zeros(NUM_DOORS, dtype=float)
        self.drive_temperature = np.full(NUM_DOORS, 20.0, dtype=float)
        self.resolver_head_raw = np.zeros(NUM_DOORS, dtype=float)
        self.resolver_head_calibrated = np.zeros(NUM_DOORS, dtype=float)
        self.open_limit_switch_engaged = np.full(NUM_LIMIT_SWITCHES, False, dtype=bool)
        self.close_limit_switch_engaged = np.full(NUM_LIMIT_SWITCHES, True, dtype=bool)
        self.locking_pins = np.full(
            NUM_LOCKING_PINS, RadLockingPinState.ENGAGED, dtype=float
        )
        self.brakes_engaged = np.full(NUM_DOORS, True, dtype=bool)
        self.photoelectric_sensor_clear = True
        self.light_curtain_clear = True
        self.power_draw = 0.0

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
                "status": [s for s in self.status],
            },
            "positionActual": self.position_actual.tolist(),
            "positionCommanded": self.position_commanded.tolist(),
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTemperature": self.drive_temperature.tolist(),
            "resolverHeadRaw": self.resolver_head_raw.tolist(),
            "resolverHeadCalibrated": self.resolver_head_calibrated.tolist(),
            "openLimitSwitchEngaged": self.open_limit_switch_engaged.tolist(),
            "closeLimitSwitchEngaged": self.close_limit_switch_engaged.tolist(),
            "lockingPins": self.locking_pins.tolist(),
            "brakesEngaged": self.brakes_engaged.tolist(),
            "photoelectricSensorClear": self.photoelectric_sensor_clear,
            "lightCurtainClear": self.light_curtain_clear,
            "powerDraw": self.power_draw,
            "timestampUTC": current_tai,
        }
        self.log.debug(f"rad_state = {self.llc_status}")

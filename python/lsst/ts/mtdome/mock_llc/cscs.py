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

__all__ = ["CscsStatus"]

import logging

from lsst.ts.xml.enums.MTDome import MotionState

from .base_mock_llc import BaseMockStatus


class CscsStatus(BaseMockStatus):
    """Represents the status of the Calibration Screen Control System in
    simulation mode.

    The Calibration Screen is not under cRIO control. The cRIO only reports its
    status so the power draw can be taken into account by the power management.

    Parameters
    ----------
    start_tai: `float`
        The TAI time, unix seconds, at the time at which this class is
        instantiated. To model the real dome, this should be the current time.
        However, for unit tests it can be convenient to use other values.
    """

    def __init__(self, start_tai: float) -> None:
        super().__init__()
        self.log = logging.getLogger("MockCalibrationScreenStatus")

        # Variables holding the status of the mock Calibration Screen.
        self.status = MotionState.STOPPED
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.position_actual = 0.0
        self.position_commanded = 0.0
        self.drive_torque_actual = 0.0
        self.drive_torque_commanded = 0.0
        self.drive_current_actual = 0.0
        self.drive_temperature = 20.0
        self.encoder_head_raw = 0.0
        self.encoder_head_calibrated = 0.0
        self.power_draw = 0.0

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.

        Parameters
        ----------
        current_tai: `float`
            The TAI time, unix seconds, for which the status is requested. To
            model the real dome, this should be the current time. However, for
            unit tests it can be convenient to use other values.
        """
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": MotionState.STOPPED.name,
                "operationalMode": self.operational_mode.name,
            },
            "positionActual": self.position_actual,
            "positionCommanded": self.position_commanded,
            "driveTorqueActual": self.drive_torque_actual,
            "driveTorqueCommanded": self.drive_torque_commanded,
            "driveCurrentActual": self.drive_current_actual,
            "driveTemperature": self.drive_temperature,
            "encoderHeadRaw": self.encoder_head_raw,
            "encoderHeadCalibrated": self.encoder_head_calibrated,
            "powerDraw": self.power_draw,
            "timestampUTC": current_tai,
        }
        self.log.debug(f"lwscs_state = {self.llc_status}")

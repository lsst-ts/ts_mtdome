# This file is part of ts_mtdome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
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

__all__ = ["ApscsStatus", "NUM_SHUTTERS", "POWER_PER_MOTOR"]

import logging

import numpy as np

from ..enums import LlcMotionState
from .base_mock_llc import BaseMockStatus
from .mock_motion.shutter_motion import (
    CLOSED_POSITION,
    NUM_MOTORS_PER_SHUTTER,
    OPEN_POSITION,
    ShutterMotion,
)

NUM_SHUTTERS = 2

# Total power drawn by the Aperture Shutter [kW] as indicated by the vendor.
_TOTAL_POWER = 5.6
# Power drawn per motor by the Aperture Shutter [kW].
POWER_PER_MOTOR = _TOTAL_POWER / NUM_SHUTTERS / NUM_MOTORS_PER_SHUTTER


class ApscsStatus(BaseMockStatus):
    """Represents the status of the Aperture Shutter Control System in
    simulation mode.

    Parameters
    ----------
    start_tai: `float`
        The TAI time, unix seconds, at the time at which this class is
        instantiated.  To model the real dome, this should be the current time.
        However, for unit tests it can be convenient to use other values.
    """

    def __init__(self, start_tai: float) -> None:
        super().__init__()
        self.log = logging.getLogger("MockApscsStatus")

        # Keep track of the state of the mock Shutter motions, one per shutter.
        self.shutter_motion = [
            ShutterMotion(start_position=CLOSED_POSITION, start_tai=start_tai),
            ShutterMotion(start_position=CLOSED_POSITION, start_tai=start_tai),
        ]

        # Keep the end TAI time as a reference for unit tests
        self.end_tai = 0.0

        # Variables holding the status of the mock Aperture Shutter
        self.status = np.full(NUM_SHUTTERS, LlcMotionState.CLOSED.name, dtype=object)
        self.messages = [{"code": 0, "description": "No Errors"}]
        self.position_actual = np.zeros(NUM_SHUTTERS, dtype=float)
        self.position_commanded = 0.0
        self.drive_torque_actual = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.drive_torque_commanded = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        # TODO DM-35910: This variable and the corresponding status item should
        #  be renamed to contain "power" instead of "current". This needs to be
        #  discussed with the manufacturer first and will require a
        #  modification to ts_xml.
        self.drive_current_actual = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.drive_temperature = np.full(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, 20.0, dtype=float
        )
        self.resolver_head_raw = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.resolver_head_calibrated = np.zeros(
            NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER, dtype=float
        )
        self.power_draw = 0.0

    async def determine_status(self, current_tai: float) -> None:
        """Determine the status of the Lower Level Component and store it in
        the llc_status `dict`.
        """

        # Loop over all doors to collect their states.
        for index in range(NUM_SHUTTERS):
            shutter_motion = self.shutter_motion[index]
            (
                position,
                velocity,
                motion_state,
            ) = shutter_motion.get_position_velocity_and_motion_state(tai=current_tai)
            self.position_actual[index] = position
            self.status[index] = motion_state

            # Determine the current drawn by the aperture shutter.
            if motion_state == LlcMotionState.MOVING:
                self.drive_current_actual[
                    index
                    * NUM_MOTORS_PER_SHUTTER : (index + 1)
                    * NUM_MOTORS_PER_SHUTTER
                ] = POWER_PER_MOTOR
            else:
                self.drive_current_actual[
                    index
                    * NUM_MOTORS_PER_SHUTTER : (index + 1)
                    * NUM_MOTORS_PER_SHUTTER
                ] = 0.0
        self.llc_status = {
            "status": {
                "messages": self.messages,
                "status": [s.name for s in self.status],
                "operationalMode": self.operational_mode.name,
            },
            "positionActual": self.position_actual.tolist(),
            "positionCommanded": self.position_commanded,
            "driveTorqueActual": self.drive_torque_actual.tolist(),
            "driveTorqueCommanded": self.drive_torque_commanded.tolist(),
            "driveCurrentActual": self.drive_current_actual.tolist(),
            "driveTemperature": self.drive_temperature.tolist(),
            "resolverHeadRaw": self.resolver_head_raw.tolist(),
            "resolverHeadCalibrated": self.resolver_head_calibrated.tolist(),
            "powerDraw": self.power_draw,
            "timestampUTC": current_tai,
        }
        self.log.debug(f"apcs_state = {self.llc_status}")

    async def openShutter(self, start_tai: float) -> float:
        """Open the shutter.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        self.position_commanded = OPEN_POSITION
        duration = 0.0
        for i in range(NUM_SHUTTERS):
            # TODO DM-35912: Discuss returning two durations with the
            #  manufacturer and implement if agreed.
            duration = self.shutter_motion[i].set_target_position_and_velocity(
                start_tai=start_tai,
                end_position=self.position_commanded,
                motion_state=LlcMotionState.MOVING,
            )
        return duration

    async def closeShutter(self, start_tai: float) -> float:
        """Close the shutter.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        self.position_commanded = CLOSED_POSITION
        duration = 0.0
        for i in range(NUM_SHUTTERS):
            # TODO DM-35912: Discuss returning two durations with the
            #  manufacturer and implement if agreed.
            duration = self.shutter_motion[i].set_target_position_and_velocity(
                start_tai=start_tai,
                end_position=self.position_commanded,
                motion_state=LlcMotionState.MOVING,
            )
        return duration

    async def stopShutter(self, start_tai: float) -> float:
        """Stop all motion of the shutter.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        duration = 0.0
        for i in range(NUM_SHUTTERS):
            # TODO DM-35912: Discuss returning two durations with the
            #  manufacturer and implement if agreed.
            duration = self.shutter_motion[i].stop(start_tai)
        self.end_tai = start_tai + duration
        return duration

    async def go_stationary(self, start_tai: float) -> float:
        """Stop shutter motion and engage the brakes.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        duration = 0.0
        for i in range(NUM_SHUTTERS):
            # TODO DM-35912: Discuss returning two durations with the
            #  manufacturer and implement if agreed.
            duration = self.shutter_motion[i].go_stationary(start_tai)
        self.end_tai = start_tai + duration
        return duration

    async def search_zero_shutter(self, start_tai: float) -> float:
        """Search the zero position of the Aperture Shutter, which is the
        closed position. This is necessary in case the ApSCS (Aperture Shutter
        Control system) was shutdown with the Aperture Shutter not fully open
        or fully closed. For now `closeShutter` simply is called but this may
        change.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        # TODO DM-35912: Discuss returning two durations with the
        #  manufacturer and implement if agreed.
        duration = await self.closeShutter(start_tai)
        return duration

    async def exit_fault(self, start_tai: float) -> float:
        """Clear the fault state.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.

        Returns
        -------
        `float`
            The expected duration of the command [s].
        """
        duration = 0.0
        for i in range(NUM_SHUTTERS):
            # TODO DM-35912: Discuss returning two durations with the
            #  manufacturer and implement if agreed.
            duration = self.shutter_motion[i].exit_fault(start_tai)
        self.end_tai = start_tai + duration
        return duration

    async def reset_drives_shutter(self, start_tai: float, reset: list[int]) -> float:
        """Reset one or more Aperture Shutter drives.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        reset: array of int
            Desired reset action to execute on each Aperture Shutter drive: 0
            means don't reset, 1 means reset.

        Returns
        -------
        `float`
            The expected duration of the command [s].

        Raises
        ------
        ValueError
            If the 'reset' parameter has the wrong length.

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        if len(reset) != NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER:
            raise ValueError(
                f"The length of 'reset' should be {NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER} "
                f"but is {len(reset)}."
            )
        duration = 0.0
        # TODO DM-35912: Discuss returning two durations with the
        #  manufacturer and implement if agreed.
        for i in range(NUM_SHUTTERS):
            duration = self.shutter_motion[i].reset_drives(
                start_tai,
                reset[i * NUM_SHUTTERS : i * NUM_SHUTTERS + NUM_MOTORS_PER_SHUTTER],
            )
        self.end_tai = start_tai + duration
        return duration

    async def set_fault(self, start_tai: float, drives_in_error: list[int]) -> None:
        """Set the LlcMotionState of ApSCS to fault and set the drives in
        drives_in_error to error.

        Parameters
        ----------
        start_tai: `float`
            The TAI time, unix seconds, when the command was issued. To model
            the real dome, this should be the current time. However, for unit
            tests it can be convenient to use other values.
        drives_in_error : array of int
            Desired error action to execute on each Shutter drive: 0 means
            don't set to error, 1 means set to error. There should be 4 error
            actions and that is not checked.

        Raises
        ------
        ValueError
            If the 'drives_in_error' parameter has the wrong length.

        Notes
        -----
        This function is not mapped to a command that MockMTDomeController can
        receive. It is intended to be set by unit test cases.
        """
        if len(drives_in_error) != NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER:
            raise ValueError(
                f"The length of 'drives_in_error' should be {NUM_SHUTTERS * NUM_MOTORS_PER_SHUTTER}"
                f" but is {len(drives_in_error)}."
            )
        for i in range(NUM_SHUTTERS):
            self.shutter_motion[i].set_fault(
                start_tai,
                drives_in_error[
                    i * NUM_SHUTTERS : i * NUM_SHUTTERS + NUM_MOTORS_PER_SHUTTER
                ],
            )

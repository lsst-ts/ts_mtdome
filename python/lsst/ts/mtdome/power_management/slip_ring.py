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

__all__ = ["SlipRing"]

import logging

from lsst.ts import utils

from ..enums import SlipRingState
from .power_draw_constants import (
    CONTINUOUS_SLIP_RING_POWER_CAPACITY,
    MAXIMUM_COOL_DOWN_TIME,
    MAXIMUM_OVER_LOW_LIMIT_TIME,
    MAXIMUM_SLIP_RING_POWER_CAPACITY,
    OVER_LIMIT_POWER_AVAILABLE,
)


class SlipRing:
    """A state machine implementation representing a slip ring.

    The slip ring of the MTDome can handle continuous power up to a limit of 78
    kW and temporary power up to 100 kW for up to 6 minutes. After going over
    the continuous limit, it needs to cool down for up 4 minutes.

    The exact cooling down model is unknown so a model proportional to the
    maximum drawn power and the amount of time over the continuous limit is
    used.

    Parameters
    ----------
    log : `logging.Logger`
        The logger for which to create a child logger.
    index : `int`
        For now the MTDome only has one slip ring but a second one will be
        installed in the future.
    disabled : `bool`
        Is the slip ring disabled or not? Defaults to False since the currently
        available slip ring always is enabled.

    Attributes
    ----------
    state : `SlipRingState`
        The state of the slip ring used in the state machine.
    below_limit_start_time : `float`
        The time [UNIX tai seconds] at which the power draw dropped below the
        continuous limit. This is set by the state machine.
    over_limit_start_time : `float`
        The time [UNIX tai seconds] at which the power draw exceeded the
        continuous limit. This is set by the state machine.
    time_over_limit : `float`
        The time interval [UNIX tai seconds] during which the power draw
        exceeded continuous limit. This is set by the state machine.
    cooling_down_time_needed : `float`
        The time interval [UNIX tai seconds] for which the slip ring needs to
        cool down. This is set by the state machine.
    max_power_drawn : `float`
        The maximum power drawn [W] during the time where the power draw
        exceeded the continuous limit. This is set by the state machine.
    """

    def __init__(
        self,
        log: logging.Logger,
        index: int,
        disabled: bool = False,
    ) -> None:
        self.log = log.getChild(type(self).__name__)
        self.index = index
        self.disabled = disabled

        self.state = SlipRingState.BELOW_LOW_LIMIT

        self.below_limit_start_time = 0.0
        self.over_limit_start_time = 0.0
        self.time_over_limit = 0.0
        self.cooling_down_time_needed = 0.0

        self.max_power_drawn = 0.0

    def get_cool_down_time(self) -> float:
        """Get the cool down time for this slip ring.

        A simple model is assumed to calculate the cool down time. This needs
        to be replaced with the real cool down model.

        Returns
        -------
        float
            The cool down time for the slip ring.
        """
        power_over_limit_fraction = (
            0.0
            if self.max_power_drawn < CONTINUOUS_SLIP_RING_POWER_CAPACITY
            else (self.max_power_drawn - CONTINUOUS_SLIP_RING_POWER_CAPACITY)
            / OVER_LIMIT_POWER_AVAILABLE
        )
        time_over_limit_fraction = self.time_over_limit / MAXIMUM_OVER_LOW_LIMIT_TIME
        return (
            MAXIMUM_COOL_DOWN_TIME
            * power_over_limit_fraction
            * time_over_limit_fraction
        )

    def get_available_power(self, current_power_draw: float) -> float:
        """Get the available power.

        Determine whether the maximum power is available or none at all based
        on the current power draw and, if the power draw has been over the
        continuous limit, for how long. If the slip ring is disabled, the
        returned value will be zero.

        Parameters
        ----------
        current_power_draw : `float`
            The amount of power currently in use [W].

        Returns
        -------
        float
            The available power [W].

        Raises
        ------
        RuntimeError
            In case an unknown SlipRingState is encountered.
        """
        if self.disabled:
            return self._handle_disabled()
        match self.state:
            case SlipRingState.BELOW_LOW_LIMIT:
                return self._handle_below_low_limit(current_power_draw)
            case SlipRingState.OVER_LOW_LIMIT:
                return self._handle_over_low_limit(current_power_draw)
            case SlipRingState.COOLING_DOWN:
                return self._handle_cooling_down()
            case _:
                raise RuntimeError(f"Encountered unknown SlipRingState {self.state=}.")

    def _handle_disabled(self) -> float:
        """Handle the DISABLED case.

        Returns
        -------
        float
            The available power [W]. In this case, always 0.0 is returned.
        """
        return 0.0

    def _handle_below_low_limit(self, current_power_draw: float) -> float:
        """Handle the BELOW_LOW_LIMIT case.

        Transition to OVER_LOW_LIMIT if the power drawn is higher than the low
        limit.

        Parameters
        ----------
        current_power_draw : `float`
            The amount of power currently in use [W].

        Returns
        -------
        float
            The available power [W].
        """
        if current_power_draw > CONTINUOUS_SLIP_RING_POWER_CAPACITY:
            # Keep track of the maximum drawn power for calculating the cool
            # down time.
            self.max_power_drawn = max(self.max_power_drawn, current_power_draw)
            # When the power draw started exceeding the continuous limit?
            self.over_limit_start_time = utils.current_tai()
            self.state = SlipRingState.OVER_LOW_LIMIT

        return MAXIMUM_SLIP_RING_POWER_CAPACITY

    def _handle_over_low_limit(self, current_power_draw: float) -> float:
        """Handle the OVER_LOW_LIMIT case.

        Keep track of the highest amount of power drawn if still over the low
        limit. Otherwise transit to COOLING_DOWN. Also transition to
        COOLING_DOWN in case the power draw has been over the low limit for too
        long.

        Parameters
        ----------
        current_power_draw : `float`
            The amount of power currently in use [W].

        Returns
        -------
        float
            The available power [W].
        """
        if (
            utils.current_tai() - self.over_limit_start_time
            >= MAXIMUM_OVER_LOW_LIMIT_TIME
            or current_power_draw <= CONTINUOUS_SLIP_RING_POWER_CAPACITY
        ):
            self.time_over_limit = utils.current_tai() - self.over_limit_start_time
            self.cooling_down_time_needed = self.get_cool_down_time()
            # Reset the maximum drawn power.
            self.max_power_drawn = 0.0
            # When the power draw dropped below the continuous limit?
            self.below_limit_start_time = utils.current_tai()
            self.state = SlipRingState.COOLING_DOWN
            # Cooling down so no power available.
            return 0.0
        else:
            # Keep track of the maximum drawn power for calculating the cool
            # down time.
            self.max_power_drawn = max(self.max_power_drawn, current_power_draw)
            return MAXIMUM_SLIP_RING_POWER_CAPACITY

    def _handle_cooling_down(self) -> float:
        """Handle the COOLING_DOWN case.

        Transition to BELOW_LOW_LIMIT if not cooling anymore.

        Returns
        -------
        float
            The available power [W].
        """
        time_since_cooling_started = utils.current_tai() - self.below_limit_start_time
        if time_since_cooling_started <= self.cooling_down_time_needed:
            # Still cooling.
            return 0.0
        else:
            # Not cooling anymore.
            self.state = SlipRingState.BELOW_LOW_LIMIT
            return MAXIMUM_SLIP_RING_POWER_CAPACITY

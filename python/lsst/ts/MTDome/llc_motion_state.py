# This file is part of ts_MTDome.
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

__all__ = ["LlcMotionState"]

import enum


class LlcMotionState(enum.IntEnum):
    """Motion state."""

    FAULT = 0
    CLOSED = 1
    CRAWLING = 2
    MOVING = 3
    OPEN = 4
    PARKED = 5
    PARKING = 6
    STOPPED = 7
    STOPPING = 8
    # Used by the lower level components and need to be translated to
    # IDL MotionState values.
    GO_STATIONARY = 9
    STATIONARY = 10
    ERROR = 11

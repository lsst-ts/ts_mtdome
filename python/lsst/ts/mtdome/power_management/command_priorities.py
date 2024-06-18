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

from lsst.ts.xml.enums.MTDome import PowerManagementMode

from ..enums import CommandName

command_priorities: dict[PowerManagementMode, dict[str, int]] = {
    PowerManagementMode.EMERGENCY: {
        CommandName.CLOSE_LOUVERS: 1,
        CommandName.CLOSE_SHUTTER: 1,
        CommandName.CRAWL_EL: 10,
        CommandName.FANS: 10,
        CommandName.MOVE_EL: 10,
        CommandName.OPEN_SHUTTER: 10,
        CommandName.SEARCH_ZERO_SHUTTER: 10,
        CommandName.SET_LOUVERS: 10,
    },
    PowerManagementMode.MAINTENANCE: {
        CommandName.CLOSE_SHUTTER: 1,
        CommandName.CLOSE_LOUVERS: 1,
        CommandName.MOVE_EL: 10,
        CommandName.CRAWL_EL: 10,
        CommandName.FANS: 100,
        CommandName.OPEN_SHUTTER: 1000,
        CommandName.SEARCH_ZERO_SHUTTER: 1000,
        CommandName.SET_LOUVERS: 1000,
    },
    PowerManagementMode.NO_POWER_MANAGEMENT: {},
    PowerManagementMode.OPERATIONS: {
        CommandName.CLOSE_SHUTTER: 1,
        CommandName.CLOSE_LOUVERS: 1,
        CommandName.OPEN_SHUTTER: 10,
        CommandName.SEARCH_ZERO_SHUTTER: 10,
        CommandName.CRAWL_EL: 100,
        CommandName.MOVE_EL: 100,
        CommandName.SET_LOUVERS: 1000,
        CommandName.FANS: 10000,
    },
}

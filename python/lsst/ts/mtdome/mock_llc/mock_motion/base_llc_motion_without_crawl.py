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

from ...enums import LlcMotionState
from .base_llc_motion import BaseLlcMotion


class BaseLlcMotionWithoutCrawl(BaseLlcMotion):
    def set_target_position_and_velocity(
        self,
        start_tai: float,
        end_position: float,
        motion_state: LlcMotionState,
    ) -> float:
        return self.base_set_target_position_and_velocity(
            start_tai=start_tai,
            end_position=end_position,
            motion_state=motion_state,
        )

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

import typing

# For an explanation why these next lines are so complicated, see
# https://confluence.lsstcorp.org/pages/viewpage.action?spaceKey=LTS&title=Enabling+Mypy+in+Pytest
if typing.TYPE_CHECKING:
    __version__ = "?"
else:
    try:
        from .version import *
    except ImportError:
        __version__ = "?"

from .config_schema import CONFIG_SCHEMA
from .llc_motion_state import LlcMotionState
from .mock_controller import *
from .mtdome_csc import *
from .on_off import OnOff
from .response_code import ResponseCode

from . import llc_configuration_limits
from . import mock_llc

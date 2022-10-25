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

__all__ = ["support_command"]

from lsst.ts import idl, salobj


def support_command(command_name: str) -> bool:
    """Check if the CSC supports a particular command.

    This is used to provide backward compatibility for new commands being
    added to the CSC.

    Returns
    -------
    `bool`
        True if the CSC interface defines the command, False otherwise.
    """
    idl_metadata = salobj.parse_idl(
        "MTDome", idl.get_idl_dir() / "sal_revCoded_MTDome.idl"
    )
    return f"command_{command_name}" in idl_metadata.topic_info

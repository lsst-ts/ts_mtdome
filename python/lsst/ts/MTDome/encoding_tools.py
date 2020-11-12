# This file is part of ts_MTDome.
#
# Developed for the LSST Telescope and Site Systems.
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

import json


def encode(**params):
    """Encode the given parameters.

    The params are treated as the key, value pairs in a dict. In other words::

        {param1: value1, param2: value2, ...}


    This method should be used for all communication with the Lower Level
    Components.

    Parameters
    ----------
    **params:
        Additional parameters to encode. This may be empty.

    Returns
    -------
        An encoded string representation of the string and parameters.
     """
    return json.dumps({**params})


def decode(st):
    """Decode the given string.

    Parameters
    ----------
    st: `str`
        The string to decode.

    Returns
    -------
        A decoded Python representation of the string.
    """
    return json.loads(st)

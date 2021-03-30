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

import logging
import json
import pathlib

import jsonschema


# Logger
log = logging.getLogger("EncodingTools")


def _load_schema(schema_name):
    schema_file = (
        pathlib.Path(__file__).resolve().parents[4].joinpath("schema", schema_name)
    )
    with open(schema_file) as f:
        return json.loads(f.read())


# dict to help look up the schema to use for validation
schemas = {
    "command": _load_schema("command.jschema"),
    "timeout": _load_schema("response.jschema"),
    "AMCS": _load_schema("amcs_status.jschema"),
    "ApSCS": _load_schema("apscs_status.jschema"),
    "LCS": _load_schema("lcs_status.jschema"),
    "LWSCS": _load_schema("lwscs_status.jschema"),
    "MonCS": _load_schema("moncs_status.jschema"),
    "ThCS": _load_schema("thcs_status.jschema"),
}


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
    data = json.loads(st)
    validate(data)
    return data


def validate(data):
    """Validates the data against a JSON schema and logs an error in case the
    validation fails.

    There are eight schemas: one for the commands, one for each of six status
    command responses and one for all other command responses. This function
    determines which schema to use based on the keys in the data. Commands are
    validated as well to ensure that the simulator receives correct commands
    and this should be done by other clients too.

    Parameters
    ----------
    data: `dict`
        The data to validate. The format of the dict is explained in the
        `encode` function.

    Raises
    ------
    ValidationError:
        In case the validation fails.
    ValueError:
        In case the retrieved data doesn't contain a known key.

    """

    try:
        for k, v in schemas.items():
            if k in data.keys():
                jsonschema.validate(data, v)
                break
        else:
            log.error(f"Validation failed because no known key found in data {data!r}")
    except jsonschema.ValidationError as e:
        log.exception("Validation failed.", e)

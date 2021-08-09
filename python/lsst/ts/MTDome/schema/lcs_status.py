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

import json

from .registry import registry

registry["LCS"] = json.loads(
    """
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "response": {
      "type": "number"
    },
    "LCS": {
      "type": "object",
      "properties": {
        "status": {
          "type": "array",
          "minItems": 34,
          "maxItems": 34,
          "items": [
            {
              "type": "string"
            }
          ]
        },
        "positionActual": {
          "type": "array",
          "minItems": 34,
          "maxItems": 34,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "positionCommanded": {
          "type": "array",
          "minItems": 34,
          "maxItems": 34,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "driveTorqueActual": {
          "type": "array",
          "minItems": 68,
          "maxItems": 68,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "driveTorqueCommanded": {
          "type": "array",
          "minItems": 68,
          "maxItems": 68,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "driveCurrentActual": {
          "type": "array",
          "minItems": 68,
          "maxItems": 68,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "driveTemperature": {
          "type": "array",
          "minItems": 68,
          "maxItems": 68,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "encoderHeadRaw": {
          "type": "array",
          "minItems": 68,
          "maxItems": 68,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "encoderHeadCalibrated": {
          "type": "array",
          "minItems": 68,
          "maxItems": 68,
          "items": [
            {
              "type": "number"
            }
          ]
        },
        "powerDraw": {
          "type": "number"
        },
        "timestampUTC": {
          "type": "number"
        }
      },
      "required": [
        "status",
        "positionActual",
        "positionCommanded",
        "driveTorqueActual",
        "driveTorqueCommanded",
        "driveCurrentActual",
        "driveTemperature",
        "encoderHeadRaw",
        "encoderHeadCalibrated",
        "powerDraw",
        "timestampUTC"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "response",
    "LCS"
  ],
  "additionalProperties": false
}
    """
)

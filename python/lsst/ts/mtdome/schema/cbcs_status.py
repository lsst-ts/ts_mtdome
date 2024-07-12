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

import json

from .registry import registry

registry["CBCS"] = json.loads(
    """
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "commandId": {
      "type": "number",
      "description": "The command ID as generated by the CSC."
    },
    "response": {
      "type": "number"
    },
    "CBCS": {
      "type": "object",
      "properties": {
        "status": {
          "type": "object",
          "properties": {
            "messages": {
              "type": "array",
              "minItems": 1,
              "items": [
                {
                  "type": "object",
                  "properties": {
                    "code": {
                      "type": "number"
                    },
                    "description": {
                      "type": "string"
                    }
                  }
                }
              ],
              "required": [
                "code",
                "description"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "messages"
          ],
          "additionalProperties": false
        },
        "fuseIntervention": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": [
            {
              "type": "boolean"
            }
          ]
        },
        "smokeDetected": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": [
            {
              "type": "boolean"
            }
          ]
        },
        "highTemperature": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": [
            {
              "type": "boolean"
            }
          ]
        },
        "lowResidualVoltage": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": [
            {
              "type": "boolean"
            }
          ]
        },
        "doorOpen": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": [
            {
              "type": "boolean"
            }
          ]
        },
        "timestampUTC": {
          "type": "number"
        }
      },
      "required": [
        "status",
        "fuseIntervention",
        "smokeDetected",
        "highTemperature",
        "lowResidualVoltage",
        "doorOpen",
        "timestampUTC"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "commandId",
    "response",
    "CBCS"
  ],
  "additionalProperties": false
}
"""
)
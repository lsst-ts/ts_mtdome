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
import typing

from .registry import registry

__all__: typing.List[str] = []

registry["command"] = json.loads(
    """
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "command": {
      "enum": [
        "moveAz",
        "moveEl",
        "stopAz",
        "stopEl",
        "stop",
        "crawlAz",
        "crawlEl",
        "setLouvers",
        "closeLouvers",
        "stopLouvers",
        "openShutter",
        "closeShutter",
        "stopShutter",
        "config",
        "restore",
        "park",
        "goStationary",
        "goStationaryAz",
        "goStationaryEl",
        "goStationaryLouvers",
        "goStationaryShutter",
        "setTemperature",
        "fans",
        "inflate",
        "statusAMCS",
        "statusApSCS",
        "statusLCS",
        "statusLWSCS",
        "statusMonCS",
        "statusThCS",
        "exitFault"
      ]
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "command": {
            "const": "moveAz"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "position": {
                "type": "number"
              },
              "velocity": {
                "type": "number"
              }
            },
            "required": [
              "position",
              "velocity"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "moveEl"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "position": {
                "type": "number"
              }
            },
            "required": [
              "position"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "stopAz"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "stopEl"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "stop"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "crawlAz"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "velocity": {
                "type": "number"
              }
            },
            "required": [
              "velocity"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "crawlEl"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "velocity": {
                "type": "number"
              }
            },
            "required": [
              "velocity"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "setLouvers"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "position": {
                "type": "array",
                "minItems": 34,
                "maxItems": 34,
                "items": [
                  {
                    "type": "number"
                  }
                ]
              }
            },
            "required": [
              "position"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "closeLouvers"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "stopLouvers"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "openShutter"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "closeShutter"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "stopShutter"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "config"
          }
        }
      },
      "then": {
        "properties": {
          "settings": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
              "type": "object",
              "properties": {
                "setting": {
                  "type": "number"
                },
                "target": {
                  "enum": [
                    "jmax",
                    "vmax",
                    "amax"
                  ]
                },
                "additionalProperties": false
              }
            },
            "additionalProperties": false
          },
          "system": {
            "enum": [
              "AMCS",
              "LWSCS"
            ]
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "restore"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "park"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "goStationary"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "goStationaryAz"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "goStationaryEl"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "goStationaryLouvers"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "goStationaryShutter"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "setTemperature"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "temperature": {
                "type": "number"
              }
            },
            "required": [
              "temperature"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "fans"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "action": {
                "type": "boolean"
              }
            },
            "required": [
              "action"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "inflate"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "properties": {
              "action": {
                "type": "boolean"
              }
            },
            "required": [
              "action"
            ],
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "statusAMCS"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "statusApSCS"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "statusLCS"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "statusLWSCS"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "statusMonCS"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "statusThCS"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "command": {
            "const": "exitFault"
          }
        }
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false
          }
        }
      }
    }
  ]
}
    """
)

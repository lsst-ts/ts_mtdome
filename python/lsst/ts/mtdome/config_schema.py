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

__all__ = ["CONFIG_SCHEMA"]

import yaml

CONFIG_SCHEMA = yaml.safe_load(
    """
    $schema: http://json-schema.org/draft-07/schema#
    $id: https://github.com/lsst-ts/ts_mtdome/blob/master/python/lsst/ts/mtdome/config_schema.py
    title: MTDome v1
    description: Schema for MTDome configuration files
    type: object
    properties:
      host:
        description: IP address of the TCP/IP interface
        type: string
        format: hostname
        default: "host.docker.internal"
      port:
        description: Port number of the TCP/IP interface
        type: integer
        default: 5000
      connection_timeout:
        description: Time limit for connecting to the TCP/IP interface (sec)
        type: number
        exclusiveMinimum: 0
        default: 10
      read_timeout:
        description: Time limit for reading data from the TCP/IP interface (sec)
        type: number
        exclusiveMinimum: 0
        default: 10
    required:
      - host
      - port
      - connection_timeout
      - read_timeout
    additionalProperties: false
    """
)

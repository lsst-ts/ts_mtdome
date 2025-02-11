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

__all__ = ["CONFIG_SCHEMA"]

import yaml

CONFIG_SCHEMA = yaml.safe_load(
    """
    $schema: http://json-schema.org/draft-07/schema#
    $id: https://github.com/lsst-ts/ts_mtdome/blob/main/python/lsst/ts/mtdome/config_schema.py
    title: MTDome v4
    description: Schema for MTDome configuration files.
    type: object
    properties:
      host:
        description: IP address of the TCP/IP interface.
        type: string
        format: hostname
      csc_port:
        description: Port number of the TCP/IP interface for the CSC.
        type: integer
      eui_port:
        description: Port number of the TCP/IP interface for the EUI.
        type: integer
      connection_timeout:
        description: Time limit for connecting to the TCP/IP interface (sec).
        type: number
        exclusiveMinimum: 0
      read_timeout:
        description: Time limit for reading data from the TCP/IP interface (sec).
        type: number
        exclusiveMinimum: 0
      amcs_vmax:
        description: >-
          The maximum velocity for the Azimuth Motion Control System (deg/sec).
          Set to -1 to indicate that this value shouldn't be set.
        type: number
      amcs_amax:
        description: >-
          The maximum acceleration for the Azimuth Motion Control System (deg/sec2).
          Set to -1 to indicate that this value shouldn't be set.
        type: number
      amcs_jmax:
        description: >-
          The maximum jerk for the Azimuth Motion Control System (deg/sec3).
          Set to -1 to indicate that this value shouldn't be set.
        type: number
    required:
      - host
      - csc_port
      - eui_port
      - connection_timeout
      - read_timeout
    additionalProperties: false
    """
)

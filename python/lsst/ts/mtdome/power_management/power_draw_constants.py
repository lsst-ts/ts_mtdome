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

HIGH_PRIOTITY = 0  # High priority for scheduling commands.

# Total power draw by the Aperture Shutter [W] as indicated by the vendor.
APS_POWER_DRAW = 5600.0

# The continuous power draw of the electronic equipment [W].
CONTINUOUS_ELECTRONICS_POWER_DRAW = 1000.0

# The power draw by the fans [W] as indicated by the vendor.
FANS_POWER_DRAW = 25000.0

# Total power draw by the Louvers [W] as indicated by the vendor.
LOUVERS_POWER_DRAW = 69000.0

# Total maximum power draw by the Light Wind Screen [W] as indicated by the
# vendor. The power draw varies depending on the elevation of the screen.
LWS_POWER_DRAW = 67500.0

# Total power draw by the Overhead Bridge Crane [W] as indicated by the vendor.
OBC_POWER_DRAW = 6000.0

# Total power draw by the Rear Access Door [W] as indicated by the vendor.
RAD_POWER_DRAW = 3000.0

# The continuous slip ring power capacity [W].
# This represents how much power can be continuously drawn
# safely from the slip ring, without overheating etc.
CONTINUOUS_SLIP_RING_POWER_CAPACITY = 78000.0

# The maximum slip ring power capacity [W].
# Drawing power between the CONTINUOUS_SLIP_RING_POWER_CAPACITY and this amount
# will overheat the slip ring and must be limited to at most 6 minutes.
MAXIMUM_SLIP_RING_POWER_CAPACITY = 100000.0

# The amount of power available on top of the continuous power [kW].
OVER_LIMIT_POWER_AVAILABLE = (
    MAXIMUM_SLIP_RING_POWER_CAPACITY - CONTINUOUS_SLIP_RING_POWER_CAPACITY
)

# The maximum allowed time to be over the low power limit [s] equivalent to 6
# minutes.
MAXIMUM_OVER_LOW_LIMIT_TIME = 360.0

# Maximum cool down time for a slip ring [s] equivalent to 4 minutes.
MAXIMUM_COOL_DOWN_TIME = 240.0

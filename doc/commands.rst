.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome-commands:

####################
Lower Level Commands
####################

This document describes the commands that will be sent from the Upper Level DCS to the Lower Level Components.
This is not a finalized list and if the need arises for it, it will be modified accordingly.
The units are `AstroPy Units`_.

    .. _AstroPy Units: https://docs.astropy.org/en/stable/units/index.html#module-astropy.units.si

.. csv-table::
    :widths: 5, 5, 25, 5, 60
    :header: Command, Parameter, Type, Unit, Remarks

    "calibrateAz"
    "closeLouvers"
    "closeShutter"
    "config", "| systemID
    | settings", "| string
    | [key, value]", "| unitless
    | unitless", "| See the `Command and Configuration Protocols`_ document."
    "crawlAz", "velocity", "double", "rad/s", "Positive means in the direction of increasing azimuth, negative in the direction of decreasing azimuth."
    "crawlEl", "velocity", "double", "rad/s", "Positive means in the direction of increasing elevation, negative in the direction of decreasing elevation."
    "exitFault"
    "fans", "action", "string", "unitless", "ON or OFF"
    "goStationaryAz"
    "goStationaryEl"
    "goStationaryLouvers"
    "goStationaryShutter"
    "inflate", "action", "string", "unitless", "ON or OFF"
    "moveAz", "| position
    | velocity", "| double
    | double", "| rad
    | rad/s", "| 0 <= position < 2π
    | Positive means in the direction of increasing azimuth, negative in the direction of decreasing azimuth."
    "moveEl", "position", "double", "rad", "0 <= position < ½π"
    "openShutter"
    "park"
    "resetDrivesAz", "reset", "[int]", "unitless", "An array of 0 and 1 where 0 means do not reset and 1 means reset."
    "resetDrivesShutter", "reset", "[int]", "unitless", "An array of 0 and 1 where 0 means do not reset and 1 means reset."
    "restore"
    "searchZeroShutter"
    "setDegradedAz"
    "setDegradedEl"
    "setDegradedLouvers"
    "setDegradedMonitoring"
    "setDegradedShutter"
    "setDegradedthermal"
    "setLouvers", "position", "[double]", "unitless", "An array of positions with one position for each louver given as a percentage where 0 means closed and 100 fully open."
    "setNormalAz"
    "setNormalEl"
    "setNormalLouvers"
    "setNormalMonitoring"
    "setNormalShutter"
    "setNormalthermal"
    "setTemperature", "temperature", "double", "Celsius"
    "statusAMCS"
    "statusApSCS"
    "statusLCS"
    "statusLWSCS"
    "statusMonCS"
    "statusThCS"
    "stopAz"
    "stopEl"
    "stopLouvers"
    "stopShutter"

.. _Command and Configuration Protocols: ./protocols.html

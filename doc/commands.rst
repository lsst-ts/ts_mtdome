.. py:currentmodule:: lsst.ts.MTDome

.. _lsst.ts.MTDome-commands:

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

    "moveAz", "| position
    | velocity", "| double
    | double", "| rad
    | rad/s", "| 0 <= position < 2π
    | Positive means in the direction of increasing azimuth, negative in the direction of decreasing azimuth."
    "moveEl", "position", "double", "rad", "0 <= position < ½π"
    "stopAz"
    "stopEl"
    "stop"
    "crawlAz", "velocity", "double", "rad/s", "Positive means in the direction of increasing azimuth, negative in the direction of decreasing azimuth."
    "crawlEl", "velocity", "double", "rad/s", "Positive means in the direction of increasing elevation, negative in the direction of decreasing elevation."
    "setLouvers", "position", "[double]", "unitless", "An array of positions with one position for each louver given as a percentage where 0 means closedand 100 fully open."
    "closeLouvers"
    "stopLouvers"
    "openShutter"
    "closeShutter"
    "stopShutter"
    "config", "| systemID
    | settings", "| string
    | [key, value]", "| unitless
    | unitless", "| See the `Command and Configuration Protocols`_ document."
    "park"
    "setTemperature", "temp", "double", "Celsius"
    "fans", "action", "string", "unitless", "ON or OFF"
    "inflate", "action", "string", "unitless", "ON or OFF"
    "statusAMCS"
    "statusApSCS"
    "statusLCS"
    "statusLWSCS"
    "statusMonCS"
    "statusThCS"

.. _Command and Configuration Protocols: ./protocols.html

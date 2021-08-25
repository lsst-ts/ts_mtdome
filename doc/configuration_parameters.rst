.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome-configuration_parameters:

#####################################
 Lower Level Configuration Parameters
#####################################

AMCS (Azimuth Motion Control System)
------------------------------------

.. csv-table::
    :widths: 10, 10, 10, 10, 50
    :header: Parameter, Description, Unit, Limit, Notes

    "jmax", "Maximum jerk", "rad/sec^3", "3.0*π/180", "This could be modified up to 4.5*π/180 in a later stage."
    "amax", "Maximum acceleration", "rad/sec^2", "0.75*π/180"
    "vmax", "Maximum velocity", "rad/sec", "1.5*π/180"

LWSCS (Light Wind Screen Control System)
----------------------------------------

.. csv-table::
    :widths: 10, 10, 10, 10, 50
    :header: Parameter, Description, Unit, Limit, Notes

    "jmax", "Maximum jerk", "rad/sec^3", "3.5*π/180", "This could be modified up to 5.25*π/180 in a later stage."
    "amax", "Maximum acceleration", "rad/sec^2", "0.875*π/180"
    "vmax", "Maximum velocity", "rad/sec", "1.75*π/180"

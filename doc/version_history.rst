.. py:currentmodule:: lsst.ts.Dome

.. _lsst.ts.Dome.version_history:

###############
Version History
###############

v0.1.0
======

First release of the Dome CSC and simulator.

This version already includes many useful things:

* A functioning Dome CSC which accepts all Dome Commands defined in ts_xml
* A functioning mock controller which accepts al JSON-style commands sent by the Dome CSC
* Functioning basic mock Lower Level Components which report their statuses. The following functionality has been implemented:

  * Azimuth rotation: simulates moving and crawling by taking into account the velocity parameters. No acceleration is simulated.
  * Aperture shutter: simulates instantaneous opening and closing.
  * Louvres: simluates instantaneous opening and closing.
  * Light and Wind Screen: simulates moving and crawling by taking into account the velocity parameters. No acceleration is simulated.
  * Interlock Monitoring: only reports a status.
  * Temperature regulation: simulates instantaneous setting of the temperature

For a full overview of the commands, communication protocols and LLC statuses,
see `Dome Software Documentation`_

.. _Dome Software Documentation: https://confluence.lsstcorp.org/display/LTS/Dome+Software+Documentation

Requires:

* ts_salobj 5.15
* ts_idl
* IDL file for Dome from ts_xml 4.8

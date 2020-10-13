.. py:currentmodule:: lsst.ts.Dome

.. _lsst.ts.Dome.version_history:

###############
Version History
###############

v0.4.0
======

| The Lower Level Component simulators for AMCS and LWSCS now handle 0/360 azimuth and 0/90 elevation limits correctly.
| The Lower Level Component simulators for AMCS and LWSCS now correctly report the duration of the commands to execute.
| Added a test to verify that all code has been formatted by Black.

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for Dome from ts_xml 4.8


v0.3.0
======

| The statuses from the lower level components are not a dict in a list but a dict.
| The configuration protocol no longer has [key, value] pairs, but {target: key, setting: value} dicts.

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for Dome from ts_xml 4.8


v0.2.1
======

| Reformat code with black.
| Fix f-strings with no string substitution.
| Pin black version in meta.yaml to 19.10b0

Requires:

* ts_salobj 5.15
* ts_idl
* IDL file for Dome from ts_xml 4.8


v0.2.0
======

Added documentation regarding communication protocols, commands, response codes, component statuses and configuration parameters.

Requires:

* ts_salobj 5.15
* ts_idl
* IDL file for Dome from ts_xml 4.8

v0.1.0
======

First release of the Dome CSC and simulator.

This version already includes many useful things:

* A functioning Dome CSC which accepts all Dome Commands defined in ts_xml
* A functioning mock controller which accepts all JSON-style commands sent by the Dome CSC
* Functioning basic mock Lower Level Components which report their statuses. The following functionality has been implemented:

  * Azimuth rotation: simulates moving and crawling by taking into account the velocity parameters. No acceleration is simulated.
  * Aperture shutter: simulates instantaneous opening and closing.
  * Louvers: simluates instantaneous opening and closing.
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

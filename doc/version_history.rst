.. py:currentmodule:: lsst.ts.MTDome

.. _lsst.ts.MTDome.version_history:

###############
Version History
###############

v1.0.1
======

Changes:

* Fix conda recipe.

Requires:

* ts_salobj 6.3
* ts_idl
* IDL file for MTDome from ts_xml 8.0

v1.0.0
======

Changes:

* Updates for ts_xml 8.0 and ts_salobj 6.3

Requires:

* ts_salobj 6.3
* ts_idl
* IDL file for MTDome from ts_xml 8.0

v0.7.2
======

Changes:

* Disabled several unit test cases.

Requires:

* ts_salobj 6.1
* ts_idl
* IDL file for MTDome from ts_xml 7.0

v0.7.1
======

Changes:

* Small fixes related to the JSON schemas.

Requires:

* ts_salobj 6.1
* ts_idl
* IDL file for MTDome from ts_xml 7.0

v0.7.
======

Changes:

* Added validation of outgoing and incoming JSON data based on JSON schemas.

Requires:

* ts_salobj 6.1
* ts_idl
* IDL file for MTDome from ts_xml 7.0

v0.6.1
======

Changes:

* Update Jenkinsfile.conda to use the shared library.
* Pin the versions of ts_idl and ts_salobj in conda/meta.yaml.

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for MTDome from ts_xml 7.0

v0.6.0
======

* Switched to pre-commit
* Switched to ts-conda-build
* Switched to JenkinsShared for the conda build
* Small code updates due to modifications in ts_xml for MTDome

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for MTDome from ts_xml 7.0


v0.5.0
======

* Renamed Dome to MTDome.
* Documentation moved to  `New Dome Software Documentation`_

.. _New Dome Software Documentation: https://ts-mtdome.lsst.io

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for MTDome from ts_xml 7.0


v0.4.0
======

* The Lower Level Component simulators for AMCS and LWSCS now handle 0/360 azimuth and 0/90 elevation limits correctly.
* The Lower Level Component simulators for AMCS and LWSCS now correctly report the duration of the commands to execute.
* Added a test to verify that all code has been formatted by Black.

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for Dome from ts_xml 4.8


v0.3.0
======

* The statuses from the lower level components are not a dict in a list but a dict.
* The configuration protocol no longer has [key, value] pairs, but {target: key, setting: value} dicts.

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for Dome from ts_xml 4.8


v0.2.1
======

* Reformat code with black.
* Fix f-strings with no string substitution.
* Pin black version in meta.yaml to 19.10b0

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

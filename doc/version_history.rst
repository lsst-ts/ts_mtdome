.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome.version_history:

###############
Version History
###############

v1.7.2
======
* Modernize Jenkinsfile.
* Add emitting the evt_azConfigurationApplied event.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 11.2

v1.7.1
======
* Fix a unit test that occasionally failed due to timing issues by removing the checks for events and adding a missing state transition.
* Fix another unit test that was waiting for an event that never got emitted.
* Implement the dome zero point offset of 32 degrees.
* Temporarily disable LWSCS commands because of the upcoming TMA pointing test.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 11

v1.7.0
======

Changes:

* Improved handling of ERROR in the MockController.
* Added the resetDrivesAz and calibrateAz commands.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 11

v1.6.0
======

Changes:

* Prepare for salobj 7.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 11

v1.5.1
======

Changes:

* Add network error handling.

Requires:

* ts_salobj 6.3
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 10.2

v1.5.0
======

Changes:

* Add "appliedConfiguration" to the status replies of AMCS and LWSCS.
* Add additional LLC states that are translated into MOVING, STOPPING or PARKING.
* Update the documentation to contain the full list of LLC commands and statuses.
* Update the MockController to handle the new state transitions.
* Fix a new mypy error by not checking DM's `lsst/__init__.py` files.
* Add new MotionStates to IDL.

Requires:

* ts_salobj 6.3
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 10.2

v1.4.0
======

Changes:

* Modify the unit tests because of changes in IDL.
* Replace the use of ts_salobj functions with ts_utils functions.
* Adde auto-enable capability.
* Rename "error" to "messages" in the status telemetry.
* Add "operationalMode" to the status telemetry.
* Add commands and events to change the operational mode of a lower level component.
* Modernize the unit tests.

Requires:

* ts_salobj 6.3
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 10.0

v1.3.0
======

Changes:

* Change the ApSCS positionActual from one to two values.
* Add type annotations.
* Rewrite the way the JSON schemas are loaded.
* Update the error part of the AMCS, ApSCS, LCS, LWSCS and ThCS status replies.
* Rename the project to ts_mtdome.
* Rename the top level Python module to lsst.ts.mtdome.

Requires:

* ts_salobj 6.3
* ts_idl
* IDL file for MTDome from ts_xml 10.0

v1.2.0
======

Changes:

* Add the exitFault, goStationary and restore commands.
* Rename the resolver telemetry items to barcodeHead and added a barcodeHead item.

Requires:

* ts_salobj 6.3
* ts_idl
* IDL file for MTDome from ts_xml 9.1

v1.1.0
======

Changes:

* Remove the use of asynctest
* Upgrade the version of Black to 20.8b1
* Upgrade the version of ts-conda-build to 0.3

Requires:

* ts_salobj 6.3
* ts_idl
* IDL file for MTDome from ts_xml 8.0

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

* Disable several unit test cases.

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

* Add validation of outgoing and incoming JSON data based on JSON schemas.

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

* Switch to pre-commit
* Switch to ts-conda-build
* Switch to JenkinsShared for the conda build
* Small code updates due to modifications in ts_xml for MTDome

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for MTDome from ts_xml 7.0


v0.5.0
======

* Rename Dome to MTDome.
* Move documentation to  `New Dome Software Documentation`_

.. _New Dome Software Documentation: https://ts-mtdome.lsst.io

Requires:

* ts_salobj 6.0
* ts_idl
* IDL file for MTDome from ts_xml 7.0


v0.4.0
======

* The Lower Level Component simulators for AMCS and LWSCS now handle 0/360 azimuth and 0/90 elevation limits correctly.
* The Lower Level Component simulators for AMCS and LWSCS now correctly report the duration of the commands to execute.
* Add a test to verify that all code has been formatted by Black.

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

Add documentation regarding communication protocols, commands, response codes, component statuses and configuration parameters.

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

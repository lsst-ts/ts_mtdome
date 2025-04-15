.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome.version_history:

###############
Version History
###############

======
v2.0.7
======
* Handle the capacitor banks dcBusVoltage telemetry item.

======
v2.0.6
======
* Fix several unit test issues.
* Suppress superfluous operationalMode events.

======
v2.0.5
======
* Query the status of thermal control.

======
v2.0.4
======
* Query the status of capacitor bank and aperture shutter.

======
v2.0.3
======
* Fix an issue with calling an unsupported status command when connected to the summit.

Requires:

* ts_salobj 7
* ts_idl
* ts_mtdomecom
* ts_xml 22.0

======
v2.0.2
======
* Mute kafka related logging.
* Add pytest option to pyproject.toml.
* Make sure that the capacitor banks telemetry has the correct data types.
* Split up exitFault to one command per subsystem.
* Move infrastructure to request subsystem statuses regularly to MTDomeCom.
* Add distinction between ports for CSC and EUI.

Requires:

* ts_salobj 7
* ts_idl
* ts_mtdomecom
* ts_xml 22.0

======
v2.0.1
======
* Update the use of LLC constants.

Requires:

* ts_salobj 7
* ts_idl
* ts_mtdomecom
* ts_xml 22.0

======
v2.0.0
======
* Move all non-CSC code and documentation to `ts_mtdomecom`.

Requires:

* ts_salobj 7
* ts_idl
* ts_mtdomecom
* ts_xml 22.0

=======
v1.18.2
=======
* Ensure that aperture shutter position values cannot be negative.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 22.0

=======
v1.18.1
=======
* Fix status command errors.
* Add check for `appliedConfiguration` key in AMCS telemetry.
* Avoid exception when canceling status command tasks.
* Add debug statements.
* Disable status commands for subsystems on the rotating part.
* Implement workaround for missing telemetry.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 22.0

=======
v1.18.0
=======
* Remove backward compatibility with XML 21.0.
* Remove duplicate moveAz command check.
* Correctly stop background tasks.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 22.0

v1.17.0
=======
* Remove backward compatibility with ts_xml 20.3.
* Remove "operationalMode" from the mock RAD status.
* Add support for the capacitor banks state event.
* Improve notifying of duplicate commands.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 21.0

v1.16.0
=======
* Remove backward compatibility with ts_xml 20.2.
* Add do_setPowerManagementMode command.
* Fix conda recipe.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.3

v1.15.7
=======
* Fix a bug in the louvers state machine.
* Implement the aperture shutter and azimuth rotation state machines.
* Consolidate remaining mock_motion code into existing code.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.6
=======
* Make sure that the shutter position cannot exceed 100%.
* Update the version of ts-conda-build to 0.4 in the conda recipe.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.5
=======
* Log a warning message when a duplicate moveAz command is received.
  Duplicate moveAz commands get ignored and that was not visible to the operators.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.4
=======
* Set log level for local run script to DEBUG.
* Rename the calibrateAz command to setZeroAz.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.3
=======
* Add temporary InternalMotionState values.
* Improve handling of InternalMotionState values.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.2
=======
* Increase frequency of all low frequency status commands.
* Workaround for missing "commandId" in command replies.
* Remove workaround for handling IDLE state.
* Disable all status commands to avoid overloading the CSC during unit tests.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.1
=======
* Add new response codes.
* Take CSCS, RAD, OBC power draw into account.
* Add LCS state machine infrastructure.
* Add ThCS state machine infrastructure.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.15.0
=======
* Switch to do_fans and do_inflate commands.
* Improve unit test code.
* Add test for the statusRAD command.
* Add support for the statusCSCS command.

These changes require at least ts_xml 20.2 and will not work with ts_xml 20.1 or before.

Requires:

* ts_salobj 7
* ts_idl
* ts_tcpip 2.0
* ts_utils 1.2
* ts_xml 20.2

v1.14.1
=======
* Add and use slip ring state machine.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* ts_xml 20.0

v1.14.0
=======
* Replace ts_idl enums with ts_xml ones.
* Reduce complexity of the "request_and_send_llc_status" command.
* Replace all string command names with an enum.
* Remove check for missing commandId.
* Start implementing power management.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* ts_xml 20.0

v1.13.0
=======
* Set ApsCS positionCommanded to two values.
* Add RAD status.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* ts_xml 20.0

v1.12.13
========
* Make azimuth rotation remember its position.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* IDL file for MTDome from ts_xml 16.0

v1.12.12
========
* Suppress "command has not received a reply" warnings.
* Remove backward compatibility with older XML versions.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* IDL file for MTDome from ts_xml 16.0

v1.12.11
========
* Explicitly use the value of string enums.
  This apparently is necessary for Python 3.11.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* IDL file for MTDome from ts_xml 16.0

v1.12.10
========
* Make sure that all config schemas get loaded.
* Make sure that the CSC can handle data from the control software without a commandId.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* IDL file for MTDome from ts_xml 16.0

v1.12.9
=======
* Add a 'commandId' to all commands and replies and handle commands with no replies after a certain time limit.
* Add two more ResponseCodes.
* Fix dunder and imports order.
* Make MockMTDomeController a subclass of tcpip.OneClientReadLoopServer.
  This requires ts_tcpip 1.1.
* Use tcpip.Client in the CSC.
  This requires ts_tcpip 1.1.
* Remove support for scons.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_tcpip 1.1
* ts_utils 1.0
* IDL file for MTDome from ts_xml 16.0

v1.12.8
=======
* Switch to using ts_pre_commit_conf.
* Silently ignore repeated moveAz commands for the same position and velocity == 0.0.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 16.0

v1.12.7
=======
* Update pre-commit hook versions.
* Remove DISABLED Motion State translation.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.6
=======
* Enable the possibility to set the maximum velocity, acceleration and jerk for the azimuth rotation via the configuration.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.5
=======
* Fix a division by zero error when crawling in AZ with the mock controller.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.4
=======
* Update the pre-commit configuration.
* Fix a mypy issue.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.3
=======
* Correct azTarget event in case of a park command.
* Add debug log statements for the commands received.
* Add workaround for IDLE state.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.2
=======
* Clear the Enabled event faultCode when necessary.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.1
=======
* Document the simulation modes.
* Switch from py.test to pytest.
* Enable all commands in simulation mode and only some in operation mode.
* Send Enabled events when the lower level components exit from FAULT state.
* Correct the MTDome zero point offset implementation.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.12.0
=======
* Disable polling the status of all subsystems except AMCS.
* Introduce backward compatibility with XML 12.0 for the TMA Pointing Test.
* Replace MTDome control software states with the ones from IDL.
* Introduce a new simulation mode, where the MockController doesn't get started by the CSC, for test purposes.
* Improve starting and stopping of MockController.
* Improve error handling of the CSC 'write then read' loop.
* The mock controllers now report the true current and power consumptions.
* The mock ApSCS controller now reports the maximum duration in case there are multiple.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.0

v1.11.3
=======
* Refactor the other test cases to contain less duplicate code.
* Rename the 'searchZeroShutter' command to 'home' and make it apply to all subsystems.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.1

v1.11.2
=======
* Refactor the AMCS test cases to contain less duplicate code.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.1

v1.11.1
=======
* Refactor the BaseLlcMotion class to have subclasses with and without crawl.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.1

v1.11.0
=======
* Restore black, flake8 and mypy pytest configuration options.
* Add ShutterMotion class for mocking the Aperture Shutter state machine.
* Add power consumption to AMCS, SpSCS, LCS and LWSCS.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.1

v1.10.0
=======
* Sort imports with isort.
* Install new pre-commit hooks.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.1

v1.9.0
======
* Re-enable the shutter commands.
* Add the searchZeroShutter and resetDrivesShutter commands.
* Add support for multiple Python versions for conda.
* Modernize type annotations.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 12.1

v1.8.0
======
* Modernize pre-commit config versions.
* Switch to pyproject.toml.
* Use entry_points instead of bin scripts.
* Disable all non-azimuth rotation related commands.

Requires:

* ts_salobj 7.0
* ts_idl
* ts_utils 1.0
* IDL file for MTDome from ts_xml 11.2

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

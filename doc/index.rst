.. py:currentmodule:: lsst.ts.Dome

.. _lsst.ts.Dome:

##############
lsst.ts.Dome
##############

Controller for the Simonyi Survey Telescope dome at Vera C. Rubin Observatory.

.. _lsst.ts.Dome-using:

Using lsst.ts.salobj
====================

.. toctree::
    protocols
    commands
    component_statuses
    configuration_parameters
    response_codes
    :maxdepth: 2

Build and Test
--------------

This package has the following requirements:

* ts_salobj

The package is compatible with LSST DM's ``scons`` build system and ``eups`` package management system.
Assuming you have the basic LSST DM stack installed you can do the following, from within the package directory:

* ``setup -r .`` to setup the package and dependencies.
* ``scons`` to build the package and run unit tests.
* ``scons install declare`` to install the package and declare it to eups.
* ``package-docs build`` to build the documentation.
  This requires ``documenteer``; see `building single package docs`_ for installation instructions.

Usage
-----

The primary classes are:

* `DomeCsc`: controller for the Simonyi Survey Telescope dome.
* `MockDomeController`: simulator for the dome TCP/IP interface.

Run the ``Dome`` controller  using ``bin/run_Dome.py`` (which only exists after you build the package).

.. _building single package docs: https://developer.lsst.io/stack/building-single-package-docs.html

.. _lsst.ts.Dome-contributing:

Contributing
============

``lsst.ts.Dome`` is developed at https://github.com/lsst-ts/ts_Dome.
You can find Jira issues for this module using `labels=ts_Dome <https://jira.lsstcorp.org/issues/?jql=project%20%3D%20DM%20AND%20labels%20%20%3D%20ts_Dome>`_.

.. _lsst.ts.Dome-pyapi:

Python API reference
====================

.. automodapi:: lsst.ts.Dome
    :no-main-docstr:

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1

.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome:

##############
lsst.ts.mtdome
##############

Controller for the Simonyi Survey Telescope dome at Vera C. Rubin Observatory.

.. _lsst.ts.mtdome-using:

Using lsst.ts.mtdome
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

* `MTDomeCsc`: controller for the Simonyi Survey Telescope dome.
* `MockDomeController`: simulator for the dome TCP/IP interface.

Run the ``MTDome`` controller  using ``bin/run_mtdome.py``.

.. _building single package docs: https://developer.lsst.io/stack/building-single-package-docs.html

.. _lsst.ts.mtdome-contributing:

Contributing
============

``lsst.ts.mtdome`` is developed at https://github.com/lsst-ts/ts_mtdome.
You can find Jira issues for this module using `labels=ts_mtdome <https://jira.lsstcorp.org/issues/?jql=project%3DDM%20AND%20labels%3Dts_mtdome>`_.

.. _lsst.ts.mtdome-pyapi:

Python API reference
====================

.. automodapi:: lsst.ts.mtdome
    :no-main-docstr:

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1

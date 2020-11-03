.. py:currentmodule:: lsst.ts.MTDome

.. _lsst.ts.MTDome:

##############
lsst.ts.MTDome
##############

Controller for the Simonyi Survey Telescope dome at Vera C. Rubin Observatory.

.. _lsst.ts.MTDome-using:

Using lsst.ts.MTDome
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

.. _lsst.ts.MTDome-contributing:

Contributing
============

``lsst.ts.MTDome`` is developed at https://github.com/lsst-ts/ts_MTDome.
You can find Jira issues for this module using `labels=ts_MTDome <https://jira.lsstcorp.org/issues/?jql=project%3DDM%20AND%20labels%3Dts_MTDome>`_.

.. _lsst.ts.MTDome-pyapi:

Python API reference
====================

.. automodapi:: lsst.ts.MTDome
    :no-main-docstr:

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1

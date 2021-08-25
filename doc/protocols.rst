.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome-protocols:

#######################
Communication Protocols
#######################

This page describes the communication protocols used by the `MTDomeCSC` to communicate with the Lower Level Components.

Command Protocol
----------------

Using JSON, this is how the command string should be constructed:

* The various components are grouped in key, value pairs.
* Any value may be another collection of key, value pairs.
* For any command, the the string "command" is a key and the name of the command the value.
  This will be followed by a "parameters" key and the value will be the command parameters as a collection of key, value pairs.
  If a command doesn't take any parameters then the value will be empty.
  In that case, the parameters key may also be omitted.
* Any command will immediately result in a reply.
  The reply will always contain two key, value pairs.
  One key will be "response" with a numeric response code as value.
  The other key will be "timeout" with the timeout as numeric value.
  The list of response codes and their meaning can be found here: `Software Response Codes`_.

  * If the reply is 0 (meaning OK) then it should be accompanied by a timeout value indicating how long it will take to execute the command.

    * The reply to a status command should be given immediately and the timeout value will omitted.
      The lower level component status returned with the reply will be part of the same message and should be added as a separate key, value pair with the short name of the lower level component as key and a collection of the status parameters with their values as value.

  * If the reply is larger than 0 (meaning ERROR) then the value indicates the error code and the timeout should be set to -1.

* Strings should be enclosed in single or double quotes.
  Numerical values should not be enclosed in quotes.
* Any resulting protocol string should be terminated by CR+LF ('\r\n').

.. _Software Response Codes: ./response_codes.html

For example, commands should be constructed like this:

.. code-block:: json

   {
     "command": "openShutter",
     "parameters": {}
   }
   {
     "command": "moveAz",
     "parameters": {
       "azimuth": 1.3962634015954636,
       "azRate": 0.001
     }
   }

Replies should be formatted like this

.. code-block:: json

    {
      "response": 0,
      "timeout": 20
    }
    {
      "response": 2,
      "timeout": -1
    }

Status commands, similarly, look like this

.. code-block:: json

    {
      "command": "statusAMCS",
      "parameters": {}
    }
    {
      "command": "statusLCS",
      "parameters": {}
    }


Configuration Protocol
----------------------

When configuration parameters are sent, the complete set of configuration parameters for one lower level component will be sent at the same time from the upper level to the lower level.
This way the other sub-systems can continue operations while the sub-system(s) that receive configuration parameters can reconfigure themselves.
This means that all parameters and their values of the sub-system will be sent together, even the ones for which the value has not changed.
This way it can be ensured that always all changes are sent and that no parameter gets forgotten.
The upper level component will check and verify that all parameter values fall within the minimum and maximum allowed values for each individual parameter.
However, since actual hardware can break it would be necessary for the lower level components to check the configuration parameters as well before applying them.

For the format of the protocol, the system gets specified separately and the configuration parameters to set are specified as an array of [target, setting] pairs.
Due to limitations in the LabVIEW JSON support, both the value for the settings keyword and the values for the parameters always need to be arrays, even if only a single value is specified.
So this means that the protocol will be of the form

.. code-block:: json

   {
     "command": "config",
     "parameters": {
       "system": "SYSTEM_ID",
       "settings": [
         {
           "target": "ParamX",
           "setting": ["Value1"]
         },
         {
           "target": "ParamY",
           "setting": ["Value1", "Value2", "Value3"]
         }
       ]
     }
   }

The reply to the command should be OK with a timeout.
The timeout signifies the amount of time needed for the lower level component to verify and apply the configuration parameters.
During the timeout no other commands should be accepted by the sub-system except the status command.

If one or more of the parameters could not be configured correctly then this should be reflected in the reply to the status command.
If one or more of the proposed values of the parameters fall outside of the range of the minimum and maximum values then none of the parameters should be applied.
It therefore is essential to check all values first and to only apply all of them once it has been verified that the values are acceptable.

If during the timeout another command except the status command is received then the reply to that command should be ERROR with an error code signifying that the system is configuring itself (the value of that error code is TBD).

A list of all configurable parameters and their maximum and minimum values can be found here: `Lower Level Configuration Parameters`_.

.. _Lower Level Configuration Parameters: ./configuration_parameters.html

JSON Schemas
------------

In order to validate the JSON messages, eight JSON schemas have been constructed.
When the schemas are used for validation, the keys in the JSON data can be used to select which schema to use.
The selection can be done for instance as follows:

* If the "command" key is present, use the command schema.
* If the "timeout" key is present, use the response schema.
* In all other cases, test for the presence of the key containing the sub-system name ("APCS", "ApSCS", etc) and use the corresponding status schema.

This is the command schema.
It looks rather complex since it covers all available commands (including the "config" command), however otherwise 24 separate schemas would need to be created.
For a full list of the commands and their parameters, see `Lower Level Commands`_.

.. _Lower Level Commands: ./commands.html

.. literalinclude:: ../python/lsst/ts/mtdome/schema/command.py
   :language: python

This is the response schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/response.py
   :language: python

This is the AMCS status schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/amcs_status.py
   :language: python

This is the ApSCS status schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/apscs_status.py
   :language: python


This is the LCS status schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/lcs_status.py
   :language: python


This is the LWSCS status schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/lwscs_status.py
   :language: python


This is the MonCS status schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/moncs_status.py
   :language: python


This is the ThCS status schema.

.. literalinclude:: ../python/lsst/ts/mtdome/schema/thcs_status.py
   :language: python


.. py:currentmodule:: lsst.ts.Dome

.. _lsst.ts.Dome-response_codes:

########################
 Software Response Codes
########################

Here is a list of agreed software error codes and their meaning. This list, as with the commands and statuses, is not necessarily complete and will be reviewed regularly.

.. list-table::
    :widths: 20, 30, 50
    :header-rows: 1

    * - Response Code
      - Meaning
      - Explanation
    * - 0
      - OK
      - Command received correctly and is being executed.
    * - 2
      - Unsupported command
      - A command was sent that is not supported by the lower level component, for instance park is sent to LCS or 'mooveAz' instead of 'moveAz' to AMCS.
    * - 3
      - Incorrect parameter(s)
      - The command that was sent is supported by the lower level component but the parameters for the command are incorrect. This can mean not enough parameters, too many parameters or one or more parameters with the wrong name.

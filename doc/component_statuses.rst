.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome-component_statuses:

###############################
 Lower Level Component Statuses
###############################

The simplest approach to this is for the status to reflect the command that currently is being executed or just has been executed.
For instance, in case of the dome AZ motion the statuses could be moving, crawling, parking, stopping, parked and stopped where moving, crawling, parking and stopping reflect that the move, crawl, park and stop commands are being executed and where parked and stopped reflect that a park, stop or move command have been executed and successfully finished.

In case of AMCS the status should not only include the status of the Dome but also if the inflatable seal has been inflated or deflated.

In case of LCS the situation is a bit more complicated since all louvers will report their status at the same time.
We should therefore use a comma separated list of statuses enclosed in square brackets, e.g. [moving, stopped, moving, moving, stopped, stopped, ...].

Following that logic, the list of statuses would be:

AMCS

    * CONFIGURING: executing the configure command
    * CRAWLING: crawling at the commanded velocity as commanded by the moveAz or the crawlAz command
    * DEFLATED: the inflate OFF command was executed
    * DEFLATING: executing the inflate OFF command
    * ERROR: an error has occurred indicated by the provided error code (TBD)
    * INFLATED: the inflate ON command was executed
    * INFLATING: executing the inflate ON command
    * MOVING: executing the moveAz command or the crawlAz command until the commanded crawl velocity has been reached
    * PARKED: the park command has been executed
    * PARKING: executing the park command
    * STOPPED: the stopAz command has been executed
    * STOPPING: executing the stopAz

These intermediate states are reported by AMCS and are automatically set by the AMCS.
These states get translated into MOVING (when PARKED or STOPPED) or STOPPING (when MOVING) by the CSC.

    * BRAKES_DISENGAGDED: the brakes have been disengaged
    * BRAKES_ENGAGDED: the brakes have been engaged
    * DISENGAGING_BRAKES: disengaging the brakes
    * DISABLING_MOTOR_POWER: disabling the motor power
    * ENABLING_MOTOR_POWER: enabling the motor power
    * ENGAGING_BRAKES: engaging the brakes
    * GO_DEGRADED: going to degraded mode
    * GO_NORMAL: going to normal mode
    * GO_STATIONARY: going to stationary mode
    * LP_DISENGAGED: the locking pins have been disengaged
    * LP_DISENGAGING: disengaging the locking pins
    * LP_ENGAGED: the locking pins have been engaged
    * LP_ENGAGING: engaging the locking pins
    * MOTOR_COOLING_OFF: the motor cooling has been switched off
    * MOTOR_COOLING_ON: the motor cooling has been switched on
    * MOTOR_POWER_OFF: the motor power has been switched off
    * MOTOR_POWER_ON: the motor power has been switched on
    * STARTING_MOTOR_COOLING: starting the motor power
    * STATIONARY: in stationary mode
    * STOPPING_MOTOR_COOLING: stopping the motor power

ApCS

    * CONFIGURING: executing the configure command
    * CLOSED: the closeShutter command has been executed
    * CLOSING: executing the closeShutter command
    * ERROR: an error has occurred indicated by the provided error code (TBD)
    * OPENING: executing the openShutter command
    * STOPPED: the stopShutter command has been executed
    * STOPPING: executing the stopShutter command

LCS

    * CONFIGURING: executing the configure command
    * ERROR: an error has occurred indicated by the provided error code (TBD)
    * MOVING: executing a setLouver command or a closeLouvers command
    * STOPPED: one of the setLouver, stopLouvers or closeLouvers command has been executed
    * STOPPING: executing a stopLouvers command

LWCS

    * CONFIGURING: executing the configure command
    * CRAWLING: crawling at the velocity commanded by yhe crawlEl command
    * ERROR: an error has occurred indicated by the provided error code (TBD)
    * MOVING: executing the moveEl command or the crawlEl command until the commanded crawl velocity has been reached
    * STOPPED: the stopEl command has been executed
    * STOPPING: executing the stopEl command

ThCS

    * CONFIGURING: executing the configure command
    * ERROR: an error has occurred indicated by the provided error code (TBD)
    * FANS_ON
    * FANS_OFF
    * SETTING: executing the setTemperature command
    * STOPPED: the stopTemperature command has been executed

MonCS

    * ALARM: the GIS system has raised an alarm
    * CONFIGURING: executing the configure command
    * ERROR: an error has occurred indicated by the provided error code (TBD)
    * NORMAL: the GIS system is normal

.. py:currentmodule:: lsst.ts.Dome

.. _lsst.ts.Dome-component_statuses:

###############################
 Lower Level Component Statuses
###############################

The simplest approach to this is for the status to reflect the command that currently is being executed or
just has been executed. For instance, in case of the dome AZ motion the statuses could be moving, crawling,
parking, stopping, parked and stopped where moving, crawling, parking and stopping reflect that the move,
crawl, park and stop commands are being executed and where parked and stopped reflect that a park, stop or
move command have been executed and successfully finished.

In case of AMCS the status should not only include the status of the Dome but also if the inflatable seal
has been inflated or deflated.

In case of LCS the situation is a bit more complicated since all louvers will report their status at the
same time. We should therefore use a comma separated list of statuses enclosed in square brackets, e.g.
[moving, stopped, moving, moving, stopped, stopped, ...].

Following that logic, the list of statuses would be:

AMCS

    * moving: executing the moveAz command or the crawlAz command until the commanded crawl velocity has been reached
    * crawling: crawling at the commanded velocity as commanded by the moveAz or the crawlAz command
    * stopping: executing the stopAz command or the stop command
    * parking: executing the park command
    * stopped: one of the stopAz or stop commands has been executed
    * parked: the park command has been executed
    * inflating: executing the inflate ON command
    * deflating: executing the inflate OFF command
    * inflated: the inflate ON command was executed
    * deflated: the inflate OFF command was executed
    * configuring: executing the configure command
    * error: an error has occurred indicated by the provided error code (TBD)

ApCS

    * opening: executing the openShutter command
    * closing: executing the closeShutter command
    * stopping: executing the stopShutter command or the stop command
    * stopped: one of the stopShutter or stop commands has been executed
    * configuring: executing the configure command
    * error: an error has occurred indicated by the provided error code (TBD)

LCS

    * moving: executing a setLouver command or a closeLouvers command
    * stopping: executing a stopLouvers command
    * stopped: one of the setLouver, stopLouvers or closeLouvers command has been executed
    * configuring: executing the configure command
    * error: an error has occurred indicated by the provided error code (TBD)

LWCS

    * moving: executing the moveEl command or the crawlEl command until the commanded crawl velocity has been reached
    * crawling: crawling at the velocity commanded by yhe crawlEl command
    * stopping: executing the stopEl command or the stop command
    * stopped: one of the stopEl, stop or moveEl commands has been executed
    * configuring: executing the configure command
    * error: an error has occurred indicated by the provided error code (TBD)

ThCS

    * setting: executing the setTemperature command
    * stopped: the setTemperature command has been executed
    * fans_on, fans_off
    * configuring: executing the configure command
    * error: an error has occurred indicated by the provided error code (TBD)

MonCS

    * normal: the GIS system is normal
    * alarm: the GIS system has raised an alarm
    * configuring: executing the configure command
    * error: an error has occurred indicated by the provided error code (TBD)
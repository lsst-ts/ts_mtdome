.. py:currentmodule:: lsst.ts.mtdome

.. _lsst.ts.mtdome-power_management:

################
Power Management
################

Introduction
============

Power for the rotating part of the dome is provided via a slip ring with a limited power capacity of 78 kW continuous, and 100 kW Peak for 6 minutes.
Since the slip ring capacity has not been derated for the thinner air at altitude, this rating should not be considered conservative.
The total power demand of all components in the rotating part of the dome is around 177.85 kW, which is significantly larger than the slip ring's capacity.
As such, power management is required to control the simultaneous operation of the various systems in order to keep the total drawn power within specification.

The slip ring demand is dominated by three systems: the Light Wind Screen (LWS), the Louvers, and the Fans.
Only one of these three components can be operated at a time.
Normally, only the LWS and the Louvers are operated at night during observing, and only the Fans are operated during the day.
Apart from these three systems, there is the Aperture Shutter (AS), which consumes relatively little.
The AS is opened at the start of an observing run and closed at the end or in case of an emergency.
The power management is achieved by the control of the cRIOs that operate the four systems.

Some of the demand systems are not controlled by the cRIOs and cannot be controlled in the power management.
These items include the Overhead Bridge Crane (OBC), Rear Access Door (RAD) and Calibration Screen.
These three items are used very infrequently.
There is also a constant power draw of the electronic devices on the rotating part of the dome.

For some systems, the power draw is continuous, while for others, power is drawn only within a short time window.

.. csv-table:: Power Draw For All Systems.
   :widths: 60, 20, 20
   :header: "System", "Power [kW]", "Duration [s]"

   Aperture Shutter, 5.6, 90
   Fans, 25.0, continuous
   Light Wind Screen, 67.5, continuous
   Louvers, 69.0, 30
   Calibration Screen {\*}, 0.75, 80
   Electronic Devices {\*}, 1.0, continuous
   Overhead Bridge Crane {\*}, 6.0, continuous
   Rear Access Door {\*}, 3.0, 90

*{\*} Power draw not managed by a cRIO.*

Since not all systems are managed by the cRIO, the power management takes the following systems under consideration:

- The Aperture Shutter.
  When starting an observing night, the aperture shutter needs to be opened.
  When the dome needs to be sealed, the aperture shutter needs to be shut.
  Although an emergency sealing procedure will be implemented, there is no purpose in operating the other systems when the shutter is being shut or opened.
  Normal shutdown operations should also not require the use of an emergency system.
- The Fans.
  The Fans are critical to operation of the thermal management system.
  However, this system only operates when the observatory is sealed and in maintenance model.
  A disruption of this system only reduces the effectiveness of the thermal control system.
  This should not endanger equipment or personnel.
  The only effect should be initial reduction in image quality during the beginning of the night observing.
  The reduction should be proportional to the duration of the disruption.
  A short duration, especially during the beginning of the day, should produce minimal to negligible image degradation.
- The Light Wind Screen.
  Observing cannot take place if the LWS is not aligned with the light path.
- The Louvers.
  This is used for sealing the dome and for regulating the air flow thru the dome.
  Regulating the air flow improves image quality, however it is not essential for observing.
  For sealing the Observatory quickly there is a separate emergency mode.

Apart from that, the electronic devices only require 1kW of power and are always on.

Power Management Modes
======================

The observatory, in general, and the dome, in particular, will be used for different purposes depending on the time of day and whether the sky is clear or not.
These different purposes have different impacts on the power draw.
Therefore several power management modes are implemented.

Operations
----------

Operations only occurs at night when the telescope engages in its mission of producing scientific images.
During operations both the LWS and the louvers must be operated.
The LWS must be operated to allow the dome to follow the clear light path of the telescope, otherwise the path will be blocked, the field of view will be obscured.
The louvers are operated to balance the effects of wind on local seeing and wind shock.
A higher wind speed minimizes the temperature differences inside the dome which minimizes the image degradation.
However, the higher wind speed increases the wind induced vibrations of the Telescope, wind shock, which reduces the image quality.
The optimum image quality occurs when these two effects are balanced.
The combined demand of the electronics, LWS and louvers of 137.5 kW is significantly larger the of 78 kW continuous, and 100 kW Peak capacities of the slip ring.

For operations, the priorities are:

1. The Electronic Devices.
2. The Aperture Shutter.
3. The Light Wind Screen.
4. The Louvers.
5. The Fans.

Maintenance
-----------

Maintenance normally occurs during the day when observing is not possible.
However, maintenance can also take place at night when observing is not possible due to inclement weather, etc.
During maintenance the dome is sealed.
The AS and the louvers remain closed.
The LWS may be operated for maintenance purposes.
The fans are a critical element of the observatory's thermal control system.
The aggregate demand during maintenance assuming LWS operation is 93.5 kW which is greater than the 78 kW continuous, but less than the 100 kW peak capacity of the slip ring.
If the OBC, RAD and calibration screen are all operated the total demand is 103 kW, which exceeds the maximum peak power.

The maintenance mode also incorporates the telescope calibration.
Most of the calibration equipment will be installed near or on the calibration screen.
This equipment includes a laser system and various electronics, all of which draw their power thru the slip ring.
Calibration requires a very acquiescent environment.
Consequently, none of the high power demand equipment can be operated during calibration, including the LWS, AS, louvers, OBC or RAD.
The fans may be operated during calibration.
This is yet to be determined.
Since none of the high demand equipment will be operated during calibration, calibration will not produce a limiting slip ring power demand.

For maintenance, the priorities are:

1. The Electronic Devices.

   The Light Wind Screen.

   The Louvers.

   The Fans.
2. The Aperture Shutter.

Emergency
---------

The dome will have a special emergency mode for sealing the dome.
The mode will be initiated when inclement weather threatens the telescope.
This mode requires that all system that are not involved in sealing the dome are disabled.
The only systems that are operational are the Electronics, the Aperture Shutter and the Louvers.
The maximum combined power demand during the emergency mode of 75.6 kW is less than the slip ring’s continuous power demand limit of 78 kW.
This mode allows the safe and rapid sealing of the dome.

For emergency, the priorities are:

1. The Electronic Devices.

   The Aperture Shutter.

   The Louvers (close only).
2. The Light Wind Screen.

   The Fans.

Implementation
==============

The dome power management is handled by the PowerManagementHandler.
This handler contains a PriorityQueue to which commands can be scheduled.
The MTDome CSC only passes on the commands that are involved with the rotating part of the dome.
These are:

- closeLouvers
- closeShutter
- crawlEl
- fans
- moveEl
- openShutter
- searchZeroShutter
- setLouvers

If the CSC receives the order to execute any of these commands, it schedules the command in the handler.
The priorities of the commands for the different PowerManagementModes are set in the handler via a dict.
The dict contains, for each PowerManagementMode, another dict of command (key) and priority (value).
The handler looks up the priority for the current PowerManagementMode of the command and schedules it accordingly.

The command priority dict is hard coded in a class and may at some point be externalized to the ts_config_mttcs project.
For all PowerManagementModes the closeShutter and closeLouvers commands have the highest priority of 1.
This was done so the dome can be sealed at any time, without the need for going to the emergency mode.
The handler may schedule commands that are not in the command priority dict.
This is the case for, for instance, all stop commands.
Those commands are scheduled with a hard coded priority of 0, since they always need to take the highest priority.

The CSC contains an async loop that regularly requests a command from the handler.
The handler requires the current power draw of each system, which is provided by the CSC when it requests the next command.
The handler uses the current power draw to determine if the command with the highest priority can be executed or not.
This is determined as follows, taking the current PowerManagementMode into account:

- If the currently highest priority command (e.g. a stop command) is not in the dict of command priorities, it gets returned.
- For commands that are in the dict of command priorities:

  - The currently highest priority command may not be executed since even higher priority commands currently are running.
    In that case no command is returned.
  - Currently running lower priority commands may need to be stopped first.
    In that case the necessary stop commands are added to the queue and no command is returned.
  - If neither of the two above are true, the currently highest priority command is returned.

For this power management implementation a conservative approach has been taken.
This means that the continuous slip ring limit of 78 kW has been taken as the only, hard, limit.
Since the electronic devices are always on and they consume 1 kW, 77 kW remains for using the other dome systems.
The consequences of this approach for the different power management modes are outlined below.

Operations
----------

For the operations mode, the hard limit means that not all systems can be used at the same time.
However, this would also be the case if the 100 kW peak capacity of the slip ring were taken into account.
Therefore, no unnecessary performance loss is introduced by the hard limit.

Maintenance
-----------

For the maintenance mode, the possible power draw scenarios pose several limitations.
When the OBC, RAD and calibration screen are not used, operating the LWS and the fans at the same time would draw more power than the hard limit.
If the OBC, RAD and calibration screen are all used, also operating the LWS and the fans at the same time would draw more power than the 100 kW peak capacity.
There are several combinations of using all five systems that may or may not exceed either the 78 kW or the 100 kW limit.
At this point it is worth repeating that the use of the OBC, RAD and calibration screen are out of control of the cRIO.
That means that if the use of any of those systems should push the total power draw beyond a limit, either the fans or the LWS need to be stopped.

The peak capacity can only be maintained for a maximum of 6 minutes, after which the slip ring needs to cool down.
It is unclear how long the slip ring needs to cool down before the power draw can safely exceed the 78 kW limit.
That probably depends on the ambient temperature.

This mode, therefore, is the most complicated one and needs to be carefully studied before considering allowing the power draw to exceed the hard limit.
If and when allowed, timers need to be included that indicate how long

- the power draw has been exceeding the 78 kW limit.
  As soon as the 6 minute limit approaches, systems may need to be stopped to make the power draw drop below the 78 kW limit again.
- the power draw has been below the 78 kW limit again.
  This is essential for letting the slip ring cool down.

Even with the conservative approach, the power draw of the OBC, RAD and calibration screen needs to be monitored at all times.
Using the electronic devices (always on!), OBC, RAD, calibration screen and LWS will push the power draw beyond the hard limit.
Since during maintenance it is expected that the fans will always be on, those need to be stopped before the LWS can be used.

Emergency
---------

For the emergency mode, the hard limit means that the fans need to be switched off and the LWS needs to be stopped.
That will leave enough power to operate the AS and louvers at the same time to seal the dome.

Changing Power Management Mode
------------------------------

In order to change power management mode, the `do_setPowerManagementMode` command can be used.
This command takes one argument: the new Power Management Mode wich is a value from the PowerManagementMode enum defined in ts_xml.
The command does not allow changing to NO_POWER_MANAGEMENT since that would put the MTDome hardware, most notably the slip ring(s), at risk.
For any other Power Management Mode the current queue of commands is emptied so they don't interfere with new commands entering the queue.
Any command that currently is being executed will continue.
The Power Management Mode priorities will make sure that any command that draws power from the slip rings will be stopped if they have a lower priority than newly scheduled commands.

Pending Items
=============

The most important pending item concerns allowing power drawn up to 100 kW for up to 6 minutes for the maintenance mode.
The current conservative approach may at times limit the freedom of using the dome systems.
Before this higher limit can be allowed, however, first it needs to be determined how long the slip ring needs to cool after having been used up to its top capacity.
It would also help to have an estimate of how often the need for more power than 78 kW is needed during maintenance to assess whether or not allowing that would be necessary.

It also needs to be decided how to change PowerManagementMode.
For this, new command definitions in ts_xml may be needed.

Completely different conditions may be needed instead.

The current implementation allows for the dome fans to be used during operations.
It is not entirely clear whether this is correct or not.

The power draw of the OBC and calibration screen is not reported yet.

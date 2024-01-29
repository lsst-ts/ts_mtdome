# This file is part of ts_mtdome.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["PowerManagementHandler"]

import asyncio
import logging

from lsst.ts.xml.enums.MTDome import OnOff

from ..enums import (
    STOP_EL,
    STOP_FANS,
    STOP_LOUVERS,
    STOP_SHUTTER,
    UNCONTROLLED_LLCS,
    CommandName,
    LlcName,
    PowerManagementMode,
    ScheduledCommand,
    StopCommand,
)
from .power_draw_constants import (
    APS_POWER_DRAW,
    FANS_POWER_DRAW,
    HIGH_PRIOTITY,
    LOUVERS_POWER_DRAW,
    LWS_POWER_DRAW,
)
from .slip_ring import SlipRing


class PowerManagementHandler:
    """Class representing the MTDome power management.

    See https://ts-mtdome.lsst.io/ for how the power management has been
    implemented.

    Parameters
    ----------
    log : `logging.Logger`
        The logger for which to create a child logger.
    command_priorities : `dict`[`PowerManagementMode`, `dict`[`str`, `int`]]
        The command priorities. All known PowerManagementModes need to be
        present. The structure is

          - PowerManagementMode 1
              - command 1 : priority 1
              - command 2 : priority 2
              ...
          - PowerManagementMode 2
              - command 1 : priority 1
              - command 2 : priority 2
              ...
          ...

    Attributes
    ----------
    command_queue : `asyncio.PriorityQueue`
        The queue of commands to be issued.
    power_management_mode : `PowerManagementMode`
        The PowerManagementMode.

    Raises
    ------
    `RuntimeError`
        In case one or more PwerManagementModes are missing.
    """

    def __init__(
        self,
        log: logging.Logger,
        command_priorities: dict[PowerManagementMode, dict[str, int]],
    ) -> None:
        missing_pmm: set[PowerManagementMode] = set()
        for power_management_mode in PowerManagementMode:
            if power_management_mode not in command_priorities:
                missing_pmm.add(power_management_mode)
        if len(missing_pmm) > 0:
            raise RuntimeError(
                "The following PowerManagementModes are missing from the configuration: "
                + ", ".join([pmm.name for pmm in missing_pmm])
            )

        self.command_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.command_priorities = command_priorities
        self.power_management_mode = PowerManagementMode.NO_POWER_MANAGEMENT
        self.log = log.getChild(type(self).__name__)
        self.slip_ring = SlipRing(log=log, index=0)

    async def schedule_command(self, command: ScheduledCommand) -> None:
        """Schedule a command to be issued.

        The priority of the command is looked up in the command_priorities for
        the current PowerManagementMode. If the command is not present then the
        DEFAULT_PRIORITY is used.

        Parameters
        ----------
        command : `ScheduledCommand`
            The command and its parameters to schedule.
        """
        priority = HIGH_PRIOTITY
        command_priorities_to_use = self.command_priorities[self.power_management_mode]
        if command.command in command_priorities_to_use:
            priority = command_priorities_to_use[command.command]
        await self.command_queue.put((priority, command))

    async def get_next_command(
        self, current_power_draw: dict[str, float]
    ) -> ScheduledCommand | None:
        """Get the next command to be issued, or None if no commands currently
        can be issued or are scheduled.

        This method delegates getting the next command to the specific method
        for the current PowerManagementMode.

        Parameters
        ----------
        current_power_draw : `dict`[`LlcName`, `float`]
            Dict of the current power draw [W] for the subsystems, or Lower
            Level Components.

        Returns
        -------
        ScheduledCommand | None
            The next command to be issued, or None if no commands currently can
            be executed or are scheduled.
        """
        if self.command_queue.empty():
            return None

        match self.power_management_mode:
            case (
                PowerManagementMode.OPERATIONS
                | PowerManagementMode.MAINTENANCE
                | PowerManagementMode.EMERGENCY
            ):
                func = getattr(
                    self, f"get_next_command_{self.power_management_mode.name.lower()}"
                )
                scheduled_command = await func(current_power_draw)
            case PowerManagementMode.NO_POWER_MANAGEMENT | _:
                _, scheduled_command = await self.command_queue.get()
        return scheduled_command

    async def get_next_command_operations(
        self, current_power_draw: dict[str, float]
    ) -> ScheduledCommand | None:
        """Get the next command to be issued, or None if no commands currently
        can be issued or are scheduled.

        This method takes the operations mode priorities into account. The
        priorities, from high to low, are:

          * Open/close the shutter.
          * Move/crawl the light/wind screen.
          * Open/close the louvers.
          * Enable the fans.

        If any higher priority command in scheduled and any lower command is
        currently being executed, the motion resulting from the lower priority
        command first is stopped. Only then the higher priority command is
        issued.
        If any lower priority command is scheduled then it will need to wait
        for the higher priority ones to finish.
        Any other command will be scheduled.

        Parameters
        ----------
        current_power_draw : `dict`[`LlcName`, `float`]
            Dict of the current power draw [W] for the subsystems, or Lower
            Level Components.

        Returns
        -------
        ScheduledCommand | None
            The next command to be issued, or None if no commands currently can
            be issued or are scheduled.

        Notes
        -----
        It is assumed that the Rear Access Door, the Overhead Bridge Crane and
        the Calibration screen are not used in this mode.
        """
        _, scheduled_command = await self.command_queue.get()
        match scheduled_command.command:
            case (
                CommandName.OPEN_SHUTTER
                | CommandName.CLOSE_SHUTTER
                | CommandName.SEARCH_ZERO_SHUTTER
            ):
                return await self.generic_get_scheduled_command_or_stop_commands(
                    scheduled_command,
                    APS_POWER_DRAW,
                    current_power_draw,
                    [STOP_EL, STOP_LOUVERS, STOP_FANS],
                    [],
                )
            case CommandName.MOVE_EL | CommandName.CRAWL_EL:
                return await self.generic_get_scheduled_command_or_stop_commands(
                    scheduled_command,
                    LWS_POWER_DRAW,
                    current_power_draw,
                    [STOP_LOUVERS, STOP_FANS],
                    [LlcName.APSCS],
                )
            case CommandName.SET_LOUVERS | CommandName.CLOSE_LOUVERS:
                return await self.generic_get_scheduled_command_or_stop_commands(
                    scheduled_command,
                    LOUVERS_POWER_DRAW,
                    current_power_draw,
                    [STOP_FANS],
                    [LlcName.APSCS, LlcName.LWSCS],
                )
            case CommandName.FANS:
                # Switching off the fans is always allowed.
                if scheduled_command.params["action"] == OnOff.OFF:
                    return scheduled_command
                else:
                    return await self.generic_get_scheduled_command_or_stop_commands(
                        scheduled_command,
                        FANS_POWER_DRAW,
                        current_power_draw,
                        [],
                        [LlcName.APSCS, LlcName.LWSCS, LlcName.LCS],
                    )
            case _:
                return scheduled_command

    async def get_next_command_maintenance(
        self, current_power_draw: dict[str, float]
    ) -> ScheduledCommand | None:
        """Get the next command to be issued, or None if no commands currently
        can be issued or are scheduled.

        This method takes the maintenance mode priorities into account. The
        priorities, from high to low, are:

          * Move/crawl the light/wind screen.
          * Enable the fans.

        If the light/wind screen is scheduled to be moved and the fans are
        currently on, the fans first are stopped. Only then the light/wind
        screen will be moved.
        If the fans are scheduled to be switched on and the light/wind screen
        currently is moving, then switching on the fans will wait until the
        light/wind screen motion is done.
        To be on the safe side, if the Aperture Shutter or Louvers are moving,
        that motion first will be stopped.
        Any other command will be refused.

        Parameters
        ----------
        current_power_draw : `dict`[`LlcName`, `float`]
            Dict of the current power draw [W] for the subsystems, or Lower
            Level Components.

        Returns
        -------
        ScheduledCommand | None
            The next command to be issued, or None if no commands currently can
            be issued or are scheduled.

        Notes
        -----
        It is assumed that the Rear Access Door, the Overhead Bridge Crane and
        the Calibration screen may, and the Aperture Shutter and Louvers may
        not be used in this mode. The latter is true so the environment inside
        the dome can be controlled.
        """
        _, scheduled_command = await self.command_queue.get()
        match scheduled_command.command:
            case CommandName.MOVE_EL | CommandName.CRAWL_EL:
                return await self.generic_get_scheduled_command_or_stop_commands(
                    scheduled_command,
                    LWS_POWER_DRAW,
                    current_power_draw,
                    [STOP_SHUTTER, STOP_LOUVERS, STOP_FANS],
                    [],
                )
            case CommandName.FANS:
                # Switching off the fans is always allowed.
                if scheduled_command.params["action"] == OnOff.OFF:
                    return scheduled_command
                else:
                    return await self.generic_get_scheduled_command_or_stop_commands(
                        scheduled_command,
                        FANS_POWER_DRAW,
                        current_power_draw,
                        [STOP_SHUTTER, STOP_LOUVERS],
                        [LlcName.LWSCS],
                    )
            case (
                CommandName.OPEN_SHUTTER
                | CommandName.CLOSE_SHUTTER
                | CommandName.SEARCH_ZERO_SHUTTER
                | CommandName.SET_LOUVERS
                | CommandName.CLOSE_LOUVERS
            ):
                # These commands are not allowed and therefore are ignored. By
                # doing so, they automatically are removed from the queue.
                return None
            case _:
                return scheduled_command

    async def get_next_command_emergency(
        self, current_power_draw: dict[str, float]
    ) -> ScheduledCommand | None:
        """Get the next command to be issued, or None if no commands currently
        can be issued or are scheduled.

        This method takes the emergency mode priorities into account. The
        commands, that may be executed, are:

          * Close the shutter.
          * Close the louvers.

        Closing shutter at the same time as closing the louvers keeps the total
        power draw under the slip ring limit.
        To be on the safe side, if the light/wind screen is moving, that motion
        first will be stopped, and if the fans are on, they will first be
        switched off.
        Any other command will be refused.

        Parameters
        ----------
        current_power_draw : `dict`[`LlcName`, `float`]
            Dict of the current power draw [W] for the subsystems, or Lower
            Level Components.

        Returns
        -------
        ScheduledCommand | None
            The next command to be issued, or None if no commands currently can
            be issued or are scheduled.

        Notes
        -----
        It is assumed that the Rear Access Door, the Overhead Bridge Crane and
        the Calibration screen are not used in this mode.
        """
        _, scheduled_command = await self.command_queue.get()
        match scheduled_command.command:
            case CommandName.CLOSE_SHUTTER | CommandName.CLOSE_LOUVERS:
                return await self.generic_get_scheduled_command_or_stop_commands(
                    scheduled_command,
                    APS_POWER_DRAW,
                    current_power_draw,
                    [STOP_EL, STOP_FANS],
                    [],
                )
            case CommandName.FANS:
                # Switching off the fans is always allowed.
                if scheduled_command.params["action"] == OnOff.OFF:
                    return scheduled_command
                else:
                    # This command is not allowed and therefore is ignored. By
                    # doing so, it automatically is removed from the queue.
                    return None
            case (
                CommandName.OPEN_SHUTTER
                | CommandName.SEARCH_ZERO_SHUTTER
                | CommandName.SET_LOUVERS
                | CommandName.MOVE_EL
                | CommandName.CRAWL_EL
            ):
                # These commands are not allowed and therefore are ignored. By
                # doing so, they automatically are removed from the queue.
                return None
            case _:
                return scheduled_command

    async def generic_get_scheduled_command_or_stop_commands(
        self,
        scheduled_command: ScheduledCommand,
        power_required: float,
        current_power_draw: dict[str, float],
        stop_commands: list[StopCommand],
        llcs_to_wait_for: list[LlcName],
    ) -> ScheduledCommand | None:
        """Get a scheduled command or schedule stop commands.

        First check the current power draw of the subsystems, or Lower Level
        Components, in llcs_to_wait_for. If the power draw is nonzero, the
        scheduled command needs to wait and None is returned.

        Then check the current power draw of the subsystems in stop_commands
        and issue a stop command for any subsystem that currently draws power.
        In that case, reschedule the schduled command and return None.

        If no stop commands were issued, return the scheduled command.

        A stop command needs to be issued if a subsystem, or Lower Level
        Component, draws power so that issuing a higher priority command would
        push the power draw over the slip ring limit.

        Parameters
        ----------
        scheduled_command : `ScheduledCommand`
            The scheduled command and its parameters.
        power_required : `float`
            The power required to execute the command.
        stop_commands : `list[`StopCommand`]
            The stop commands with their parameters and the subsystem, or Lower
            Level Component, names.
        current_power_draw : `dict`[`str`, `float`]
            See `get_next_command` for an explanation of this parameter.
        llcs_to_wait_for : `list`[`LlcName`]
            The subsystems, or Lower Level Components, to check the current
            power draw for. If the power draw is non-zero, the scheduled
            command needs to wait and will be rescheduled.

        Returns
        -------
        bool
            True if at least one stop command was scheduled, False otherwise.
        """
        # Verify that there is enough power available to execute the command.
        total_power_draw = sum(
            [power_draw for system, power_draw in current_power_draw.items()]
        )
        power_available = self.slip_ring.get_available_power(total_power_draw)
        if power_available - total_power_draw > power_required:
            return scheduled_command

        # Always wait for these LLCs, which are not controlled by the cRIO.
        llcs_to_wait_for = llcs_to_wait_for + UNCONTROLLED_LLCS

        # If not enough power is available, stop lower priority commands to
        # free up power.
        for llc_name in llcs_to_wait_for:
            if current_power_draw[llc_name] > 0:
                self.log.info(
                    f"Waiting for {llc_name.name} to finish. Rescheduling {scheduled_command.command}."
                )
                await self.schedule_command(scheduled_command)
                return None
        stop_command_issued = False
        for stop_command in stop_commands:
            stop = stop_command.scheduled_command
            if current_power_draw[stop_command.llc_name] > 0:
                # Schedule the command to stop the current motion. The priority
                # is set to 0 meaning a higher priority than all other
                # commands.
                self.log.info(
                    f"Scheduling a stop command for {stop_command.llc_name.name}."
                )
                await self.command_queue.put((HIGH_PRIOTITY, stop))
                stop_command_issued = True
            else:
                stop_command_issued = stop_command_issued | False
        if stop_command_issued:
            self.log.info(
                f"Waiting for subsystems to stop. Rescheduling {scheduled_command.command}."
            )
            await self.schedule_command(scheduled_command)
            return None
        else:
            return scheduled_command

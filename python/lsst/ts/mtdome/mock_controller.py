# This file is part of ts_mtdome.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
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

__all__ = ["MockMTDomeController"]

import asyncio
import logging
import re
import typing

from lsst.ts import tcpip, utils
from lsst.ts.mtdome import encoding_tools, mock_llc
from lsst.ts.mtdome.enums import LlcName, ResponseCode

COMMAND_ID_PATTERN = re.compile(r'"commandId": (.*?),')


class MockMTDomeController(tcpip.OneClientReadLoopServer):
    """Mock MTDome Controller that talks over TCP/IP.

    Parameters
    ----------
    port : `int`
        TCP/IP port

    Notes
    -----
    There are six sub-systems that are under control:

    * AMCS: Azimuth Motion Control System
    * ApSCS: Aperture Shutter Control System
    * LCS: Louvers Control System
    * LWSCS: Light and Wind Screen Control System
    * MonCS: Monitoring Control System, which interfaces with the MTDome
        Interlock System
    * ThCS: Thermal Control System, which interfaces with the MTDome
        Environment Control System

    To start the server:

        ctrl = MockMTDomeController(...)
        await ctrl.start()

    To stop the server:

        await ctrl.stop()

    Known Limitations:

    * Just a framework that needs to be implemented properly.
    """

    # A long sleep to mock a slow network [s].
    SLOW_NETWORK_SLEEP = 10.0
    # A long duration [s]. Used as a return value by commands.
    LONG_DURATION = 20

    def __init__(
        self,
        host: None | str,
        port: int,
        log: logging.Logger,
        connect_callback: None | tcpip.ConnectCallbackType = None,
        name: str = "",
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            log=log,
            connect_callback=connect_callback,
            name=name,
        )

        # Dict of command: (has_argument, function).
        # The function is called with:
        # * No arguments, if `has_argument` False.
        # * The argument as a string, if `has_argument` is True.
        self.dispatch_dict: dict[str, typing.Callable] = {
            "calibrateAz": self.calibrate_az,
            "closeLouvers": self.close_louvers,
            "closeShutter": self.close_shutter,
            "config": self.config,
            "crawlAz": self.crawl_az,
            "crawlEl": self.crawl_el,
            "exitFault": self.exit_fault,
            "fans": self.fans,
            "goStationaryAz": self.go_stationary_az,
            "goStationaryEl": self.go_stationary_el,
            "goStationaryLouvers": self.go_stationary_louvers,
            "goStationaryShutter": self.go_stationary_shutter,
            "inflate": self.inflate,
            "moveAz": self.move_az,
            "moveEl": self.move_el,
            "openShutter": self.open_shutter,
            "park": self.park,
            "resetDrivesAz": self.reset_drives_az,
            "resetDrivesShutter": self.reset_drives_shutter,
            "restore": self.restore,
            "searchZeroShutter": self.search_zero_shutter,
            "setDegradedAz": self.set_degraded_az,
            "setDegradedEl": self.set_degraded_el,
            "setDegradedLouvers": self.set_degraded_louvers,
            "setDegradedShutter": self.set_degraded_shutter,
            "setDegradedMonitoring": self.set_degraded_monitoring,
            "setDegradedThermal": self.set_degraded_thermal,
            "setLouvers": self.set_louvers,
            "setNormalAz": self.set_normal_az,
            "setNormalEl": self.set_normal_el,
            "setNormalLouvers": self.set_normal_louvers,
            "setNormalShutter": self.set_normal_shutter,
            "setNormalMonitoring": self.set_normal_monitoring,
            "setNormalThermal": self.set_normal_thermal,
            "setTemperature": self.set_temperature,
            "statusAMCS": self.status_amcs,
            "statusApSCS": self.status_apscs,
            "statusLCS": self.status_lcs,
            "statusLWSCS": self.status_lwscs,
            "statusMonCS": self.status_moncs,
            "statusThCS": self.status_thcs,
            "stopAz": self.stop_az,
            "stopEl": self.stop_el,
            "stopLouvers": self.stop_louvers,
            "stopShutter": self.stop_shutter,
        }
        # Time keeping
        self.current_tai = 0
        # Mock a slow network (True) or not (False). To be set by unit tests
        # only.
        self.enable_slow_network = False
        # Mock a network interruption (True) or not (False). To be set by unit
        # tests only.
        self.enable_network_interruption = False
        self.read_task: asyncio.Future | None = None

        # Keep track of the command ID.
        self._command_id = -1

        # Variables for the lower level components.
        self.amcs: typing.Optional[mock_llc.AmcsStatus] = None
        self.apscs: typing.Optional[mock_llc.ApscsStatus] = None
        self.lcs: typing.Optional[mock_llc.LcsStatus] = None
        self.lwscs: typing.Optional[mock_llc.LwscsStatus] = None
        self.moncs: typing.Optional[mock_llc.MoncsStatus] = None
        self.thcs: typing.Optional[mock_llc.ThcsStatus] = None

    async def start(self, **kwargs: typing.Any) -> None:
        """Start the TCP/IP server.

        Parameters
        ----------
        **kwargs : `dict` [`str`, `typing.Any`]
            Additional keyword arguments for `asyncio.start_server`,
            beyond host and port.
        """
        self.log.info("Start called")
        await super().start(**kwargs)

        await self.determine_current_tai()

        self.log.info("Starting LLCs")
        self.amcs = mock_llc.AmcsStatus(start_tai=self.current_tai)
        self.apscs = mock_llc.ApscsStatus(start_tai=self.current_tai)
        self.lcs = mock_llc.LcsStatus()
        self.lwscs = mock_llc.LwscsStatus(start_tai=self.current_tai)
        self.moncs = mock_llc.MoncsStatus()
        self.thcs = mock_llc.ThcsStatus()

    async def write_with_command_id(self, **data: typing.Any) -> None:
        """Write the data appended with a newline character.

        Parameters
        ----------
        data:
            The data to write.
        """
        await self.write_json({"commandId": self._command_id, **data})

    async def read_and_dispatch(self) -> None:
        try:
            # Don't use ``self.read_json`` here. Further down first the string
            # will be parsed to see if ``commandId`` is present. Only if yes,
            # the string will be JSON decoded.
            line = await self.read_str()
            self.log.debug(f"Read command line: {line!r}")
        except (asyncio.IncompleteReadError, AssertionError):
            return
        if line:
            # some housekeeping for sending a response
            send_response = True
            response = ResponseCode.OK
            try:
                # First the line needs to be parsed to get the commandId.
                # This is necessary because deconding the line with the
                # encoding tools may result in a ValidationError and then
                # the commandId cannot be retrieved from the decoded items.
                command_id_search = COMMAND_ID_PATTERN.search(line)
                if command_id_search:
                    # The group containing the commandId value needs to be
                    # retrieved, which is why group == 1 is used here.
                    command_id_string = command_id_search.group(1)
                    if command_id_string.isdigit():
                        self._command_id = int(command_id_search.group(1))
                    else:
                        raise ValueError(f"commandId is not an int in {line=}")

                # Now demarshall the line into a dict of Python objects.
                items = encoding_tools.decode(line)

                cmd = items["command"]
                self.log.debug(f"Trying to execute cmd {cmd}")
                if cmd not in self.dispatch_dict:
                    self.log.error(f"Command '{line}' unknown")
                    # CODE=2 in this case means "Unsupported command."
                    response = ResponseCode.UNSUPPORTED_COMMAND
                    duration = -1
                else:
                    if self.enable_network_interruption:
                        # Mock a network interruption: it doesn't matter if
                        # the command never is received or the reply never
                        # sent.
                        return

                    func = self.dispatch_dict[cmd]
                    kwargs = items["parameters"]
                    if cmd.startswith("status"):
                        # The status commands take care of sending a reply
                        # themselves.
                        send_response = False

                    if self.enable_slow_network:
                        # Mock a slow network.
                        await asyncio.sleep(MockMTDomeController.SLOW_NETWORK_SLEEP)

                    duration = await func(**kwargs)
            except asyncio.CancelledError:
                self.log.debug("cmd_loop ends")
                duration = -1
            except Exception:
                self.log.exception(f"Command '{line}' failed")
                # Command rejected: a message explaining why needs to be
                # added at some point but we haven't discussed that yet
                # with the vendor.
                response = ResponseCode.INCORRECT_PARAMETERS
                duration = -1
            if send_response:
                if duration is None:
                    duration = MockMTDomeController.LONG_DURATION
                # DM-25189: timeout should be renamed duration and this
                # needs to be discussed with EIE. As soon as this is done
                # and agreed upon, I will open another issue to fix this.
                await self.write_with_command_id(response=response, timeout=duration)

    async def status_amcs(self) -> None:
        """Request the status from the AMCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.amcs, LlcName.AMCS)

    async def status_apscs(self) -> None:
        """Request the status from the ApSCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.apscs, LlcName.APSCS)

    async def status_lcs(self) -> None:
        """Request the status from the LCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.lcs, LlcName.LCS)

    async def status_lwscs(self) -> None:
        """Request the status from the LWSCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.lwscs, LlcName.LWSCS)

    async def status_moncs(self) -> None:
        """Request the status from the MonCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.moncs, LlcName.MONCS)

    async def status_thcs(self) -> None:
        """Request the status from the ThCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.thcs, LlcName.THCS)

    async def request_and_send_status(
        self, llc: mock_llc.BaseMockStatus, llc_name: LlcName
    ) -> None:
        """Request the status of the given Lower Level Component and write it
        to the requester.

        Parameters
        ----------
        llc: `BaseMockStatus`
            The Lower Level Component status to request the status from.
        llc_name: `LlcName`
            The name of the Lower Level Component.
        """
        self.log.debug("Determining current TAI.")
        await self.determine_current_tai()
        self.log.debug(f"Requesting status for LLC {llc_name}")
        await llc.determine_status(self.current_tai)
        state = {llc_name: llc.llc_status}
        await self.write_with_command_id(response=ResponseCode.OK, **state)

    async def determine_current_tai(self) -> None:
        """Determine the current TAI time.

        This is done in a separate method so a mock method can replace it in
        unit tests.
        """
        self.current_tai = utils.current_tai()

    async def move_az(self, position: float, velocity: float) -> float:
        """Move the dome.

        Parameters
        ----------
        position: `float`
            Desired azimuth, in radians, in range [0, 2 pi)
        velocity: `float`
            The velocity, in rad/sec, to start crawling at once the position
            has been reached.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        assert self.amcs is not None
        return await self.amcs.moveAz(position, velocity, self.current_tai)

    async def move_el(self, position: float) -> float:
        """Move the light and wind screen.

        Parameters
        ----------
        position: `float`
            Desired elevation, in radians, in range [0, pi/2)

        Returns
        -------
        duration: `float`
            The estimated duration of the execution of the command.
        """
        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        assert self.lwscs is not None
        return await self.lwscs.moveEl(position, self.current_tai)

    async def stop_az(self) -> float:
        """Stop all dome motion.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.amcs is not None
        return await self.amcs.stopAz(self.current_tai)

    async def stop_el(self) -> float:
        """Stop all light and wind screen motion.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.lwscs is not None
        return await self.lwscs.stopEl(self.current_tai)

    async def crawl_az(self, velocity: float) -> float:
        """Crawl the dome.

        Parameters
        ----------
        velocity: `float`
            The velocity, in rad/sec, to crawl at.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        assert self.amcs is not None
        return await self.amcs.crawlAz(velocity, self.current_tai)

    async def crawl_el(self, velocity: float) -> float:
        """Crawl the light and wind screen.

        Parameters
        ----------
        velocity: `float`
            The velocity, in rad/sec, to crawl at.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        assert self.lwscs is not None
        return await self.lwscs.crawlEl(velocity, self.current_tai)

    async def set_louvers(self, position: list[float]) -> None:
        """Set the positions of the louvers.

        Parameters
        ----------
        position: array of float
            An array of positions, in percentage with 0 meaning closed and 100
            fully open, for each louver. A position of -1 means "do not move".
        """
        assert self.lcs is not None
        await self.lcs.setLouvers(position)

    async def close_louvers(self) -> None:
        """Close all louvers."""
        assert self.lcs is not None
        await self.lcs.closeLouvers()

    async def stop_louvers(self) -> None:
        """Stop the motion of all louvers."""
        assert self.lcs is not None
        await self.lcs.stopLouvers()

    async def open_shutter(self) -> float:
        """Open the shutter.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.apscs is not None
        return await self.apscs.openShutter(self.current_tai)

    async def close_shutter(self) -> float:
        """Close the shutter.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.apscs is not None
        return await self.apscs.closeShutter(self.current_tai)

    async def stop_shutter(self) -> float:
        """Stop the motion of the shutter.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.apscs is not None
        return await self.apscs.stopShutter(self.current_tai)

    async def config(self, system: str, settings: dict) -> None:
        """Configure the lower level components.

        Parameters
        ----------
        system: `str`
            The name of the system to configure.
        settings: `dict`
            An array containing a single dict with key,value pairs for all the
            parameters that need to be configured. The structure is::

                [
                    {
                      "Parameter1_name": Value,
                      "Parameter2_name": Value,
                      ...
                    }
                  ]

            It is assumed that the values of the configuration parameters are
            validated to lie within the limits before being passed on to this
            function.
            It is assumed that all configuration parameters are present and
            that their values represent the value to set even unchanged.
        """
        if system == LlcName.AMCS:
            for field in settings:
                if field["target"] in ("jmax", "amax", "vmax"):
                    # DM-25758: All param values are passed on as arrays so in
                    # these cases we need to extract the only value in the
                    # array.
                    assert self.amcs is not None
                    setattr(self.amcs, field["target"], field["setting"][0])
        elif system == LlcName.LWSCS:
            for field in settings:
                if field["target"] in ("jmax", "amax", "vmax"):
                    # DM-25758: All param values are passed on as arrays so in
                    # these cases we need to extract the only value in the
                    # array.
                    assert self.lwscs is not None
                    setattr(self.lwscs, field["target"], field["setting"][0])
        else:
            raise KeyError(f"Unknown system {system}.")

    async def restore(self) -> None:
        """Restore the default configuration of the lower level components."""
        self.log.debug("Received command 'restore'")
        # TODO: Need to find a way to store the default values for all lower
        #  level components.

    async def park(self) -> float:
        """Park the dome.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.amcs is not None
        return await self.amcs.park(self.current_tai)

    async def go_stationary_az(self) -> float:
        """Stop azimuth motion and engage the brakes. Also disengage the
        locking pins if engaged.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.amcs is not None
        return await self.amcs.go_stationary(self.current_tai)

    async def go_stationary_el(self) -> float:
        """Stop elevation motion and engage the brakes. Also disengage the
        locking pins if engaged.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.lwscs is not None
        return await self.lwscs.go_stationary(self.current_tai)

    async def go_stationary_shutter(self) -> float:
        """Stop shutter motion and engage the brakes.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.apscs is not None
        return await self.apscs.go_stationary(self.current_tai)

    async def go_stationary_louvers(self) -> None:
        """Stop louvers motion and engage the brakes."""
        assert self.lcs is not None
        await self.lcs.go_stationary()

    async def set_normal_az(self) -> None:
        """Set az operational mode to normal (as opposed to degraded)."""
        assert self.amcs is not None
        await self.amcs.set_normal()

    async def set_normal_el(self) -> None:
        """Set el operational mode to normal (as opposed to degraded)."""
        assert self.lwscs is not None
        await self.lwscs.set_normal()

    async def set_normal_shutter(self) -> None:
        """Set shutter operational mode to normal (as opposed to degraded)."""
        assert self.apscs is not None
        await self.apscs.set_normal()

    async def set_normal_louvers(self) -> None:
        """Set louvers operational mode to normal (as opposed to degraded)."""
        assert self.lcs is not None
        await self.lcs.set_normal()

    async def set_normal_monitoring(self) -> None:
        """Set monitoring operational mode to normal (as opposed to
        degraded).
        """
        assert self.moncs is not None
        await self.moncs.set_normal()

    async def set_normal_thermal(self) -> None:
        """Set thermal operational mode to normal (as opposed to degraded)."""
        assert self.thcs is not None
        await self.thcs.set_normal()

    async def set_degraded_az(self) -> None:
        """Set az operational mode to degraded (as opposed to normal)."""
        assert self.amcs is not None
        await self.amcs.set_degraded()

    async def set_degraded_el(self) -> None:
        """Set el operational mode to degraded (as opposed to normal)."""
        assert self.lwscs is not None
        await self.lwscs.set_degraded()

    async def set_degraded_shutter(self) -> None:
        """Set shutter operational mode to degraded (as opposed to normal)."""
        assert self.apscs is not None
        await self.apscs.set_degraded()

    async def set_degraded_louvers(self) -> None:
        """Set louvers operational mode to degraded (as opposed to normal)."""
        assert self.lcs is not None
        await self.lcs.set_degraded()

    async def set_degraded_monitoring(self) -> None:
        """Set monitoring operational mode to degraded (as opposed to
        normal).
        """
        assert self.moncs is not None
        await self.moncs.set_degraded()

    async def set_degraded_thermal(self) -> None:
        """Set thermal operational mode to degraded (as opposed to normal)."""
        assert self.thcs is not None
        await self.thcs.set_degraded()

    async def set_temperature(self, temperature: float) -> None:
        """Set the preferred temperature in the dome.

        Parameters
        ----------
        temperature: `float`
            The temperature, in degrees Celsius, to set.
        """
        assert self.thcs is not None
        await self.thcs.setTemperature(temperature)

    async def exit_fault(self) -> None:
        """Exit from fault state."""
        assert self.amcs is not None
        await self.amcs.exit_fault(self.current_tai)
        assert self.apscs is not None
        await self.apscs.exit_fault(self.current_tai)
        assert self.lcs is not None
        await self.lcs.exit_fault()
        assert self.lwscs is not None
        await self.lwscs.exit_fault(self.current_tai)
        assert self.moncs is not None
        await self.moncs.exit_fault()
        assert self.thcs is not None
        await self.thcs.exit_fault()

    async def inflate(self, action: str) -> None:
        """Inflate or deflate the inflatable seal.

        Parameters
        ----------
        action: `str`
            ON means inflate and OFF deflate the inflatable seal.
        """
        assert self.amcs is not None
        await self.amcs.inflate(self.current_tai, action)

    async def fans(self, action: str) -> None:
        """Enable or disable the fans in the dome.

        Parameters
        ----------
        action: `str`
            ON means fans on and OFF fans off.
        """
        assert self.amcs is not None
        await self.amcs.fans(self.current_tai, action)

    async def reset_drives_az(self, reset: list[int]) -> float:
        """Reset one or more AZ drives.

        Parameters
        ----------
        reset: array of int
            Desired reset action to execute on each AZ drive: 0 means don't
            reset, 1 means reset.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        assert self.amcs is not None
        return await self.amcs.reset_drives_az(self.current_tai, reset)

    async def reset_drives_shutter(self, reset: list[int]) -> None:
        """Reset one or more Aperture Shutter drives.

        Parameters
        ----------
        reset: array of int
            Desired reset action to execute on each Aperture Shutter drive: 0
            means don't reset, 1 means reset.

        Notes
        -----
        This is necessary when exiting from FAULT state without going to
        Degraded Mode since the drives don't reset themselves.
        The number of values in the reset parameter is not validated.
        """
        assert self.apscs is not None
        await self.apscs.reset_drives_shutter(self.current_tai, reset)

    async def calibrate_az(self) -> float:
        """Take the current position of the dome as zero. This is necessary as
        long as the racks, pinions and encoders on the drives have not been
        installed yet to compensate for slippage of the drives.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.amcs is not None
        return await self.amcs.calibrate_az(self.current_tai)

    async def search_zero_shutter(self) -> float:
        """Search the zero position of the Aperture Shutter, which is the
        closed position. This is necessary in case the ApSCS (Aperture Shutter
        Control system) was shutdown with the Aperture Shutter not fully open
        or fully closed.

        Returns
        -------
        `float`
            The estimated duration of the execution of the command.
        """
        assert self.apscs is not None
        return await self.apscs.search_zero_shutter(self.current_tai)


async def main() -> None:
    """Main method that gets executed in stand alone mode."""
    log = logging.getLogger("MockMTDomeController")
    log.info("main method")
    # An arbitrarily chosen port. Nothing special about it.
    port = 5000
    log.info("Constructing mock controller.")
    mock_ctrl = MockMTDomeController(host=tcpip.DEFAULT_LOCALHOST, port=port, log=log)
    log.info("Starting mock MTDome controller.")
    await mock_ctrl.start(keep_running=True)


if __name__ == "__main__":
    logging.info("main")
    loop = asyncio.get_event_loop()
    try:
        logging.info("Calling main method")
        loop.run_until_complete(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass

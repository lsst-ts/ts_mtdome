# This file is part of ts_Dome.
#
# Developed for the LSST Data Management System.
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

__all__ = ["MockDomeController"]

import asyncio
import logging

from lsst.ts.Dome.llc_name import LlcName
from lsst.ts import salobj
from lsst.ts.Dome import encoding_tools
from lsst.ts.Dome import mock_llc_statuses
from lsst.ts.Dome.response_code import ResponseCode


class MockDomeController:
    """Mock DomeController that talks over TCP/IP.

    Parameters
    ----------
    port : int
        TCP/IP port

    Notes
    -----
    To start the server:

        ctrl = MockDomeController(...)
        await ctrl.start()

    To stop the server:

        await ctrl.stop()

    Known Limitations:

    * Just a framework that needs to be implemented properly
    """

    def __init__(
        self, port,
    ):
        self.port = port
        self._server = None
        self._writer = None
        self.log = logging.getLogger("MockDomeController")
        # Dict of command: (has_argument, function).
        # The function is called with:
        # * No arguments, if `has_argument` False.
        # * The argument as a string, if `has_argument` is True.
        self.dispatch_dict = {
            "moveAz": self.move_az,
            "moveEl": self.move_el,
            "stopAz": self.stop_az,
            "stopEl": self.stop_el,
            "stop": self.stop_llc,
            "crawlAz": self.crawl_az,
            "crawlEl": self.crawl_el,
            "setLouvers": self.set_louvers,
            "closeLouvers": self.close_louvers,
            "stopLouvers": self.stop_louvers,
            "openShutter": self.open_shutter,
            "closeShutter": self.close_shutter,
            "stopShutter": self.stop_shutter,
            "config": self.config,
            "park": self.park,
            "setTemperature": self.set_temperature,
            "fans": self.fans,
            "inflate": self.inflate,
            "statusAMCS": self.status_amcs,
            "statusApSCS": self.status_apscs,
            "statusLCS": self.status_lcs,
            "statusLWSCS": self.status_lwscs,
            "statusMonCS": self.status_moncs,
            "statusThCS": self.status_thcs,
        }
        # Timeouts used by this class and by its unit test
        self.long_timeout = 20
        self.short_timeout = 2
        # Time keeping
        self.current_tai = 0

        # Variables to hold the status of the lower level components.
        self.amcs = mock_llc_statuses.AmcsStatus()
        self.apscs = mock_llc_statuses.ApscsStatus()
        self.lcs = mock_llc_statuses.LcsStatus()
        self.lwscs = mock_llc_statuses.LwscsStatus()
        self.moncs = mock_llc_statuses.MoncsStatus()
        self.thcs = mock_llc_statuses.ThcsStatus()

    async def start(self, keep_running=False):
        """Start the TCP/IP server.

        Start the command loop and make sure to keep running when instructed to
         do so.

        Parameters
        ----------
        keep_running : bool
            Used for command line testing and should generally be left to
            False.
        """
        self.log.info("Start called")
        self._server = await asyncio.start_server(
            self.cmd_loop, host="127.0.0.1", port=self.port
        )
        # Request the assigned port from the server so the code starting the
        # mock controller can use it to connect.
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]

        self.log.info("Starting LLCs")

        if keep_running:
            await self._server.serve_forever()

    async def stop(self):
        """Stop the mock lower level components and the TCP/IP server.
        """
        if self._server is None:
            return

        server = self._server
        self._server = None
        self.log.info("Closing server")
        server.close()
        self.log.info("Done closing")

    async def write(self, **data):
        """Write the data appended with a newline character.

        Parameters
        ----------
        data:
            The data to write.
        """
        st = encoding_tools.encode(**data)
        self._writer.write(st.encode() + b"\r\n")
        self.log.debug(st)
        await self._writer.drain()

    async def write_error(self, code):
        """Generic method for writing errors.

        Parameters
        ----------
        code: `ErrorCode`
            The error code to write.
        """
        await self.write("ERROR", CODE=code.value)

    async def cmd_loop(self, reader, writer):
        """Execute commands and output replies.

        Parameters
        ----------
        reader: stream reader
            The stream reader to read from.
        writer: stream writer
            The stream writer to write to.
        """
        self.log.info("The cmd_loop begins")
        self._writer = writer
        while True:
            self.log.debug("Waiting for next command.")
            timeout = self.long_timeout

            line = None
            try:
                line = await reader.readuntil(b"\r\n")
                line = line.decode().strip()
                self.log.debug(f"Read command line: {line!r}")
            except asyncio.IncompleteReadError:
                return
            if line:
                # some housekeeping for sending a response
                send_response = True
                response = ResponseCode.OK
                try:
                    # demarshall the line into a dict of Python objects.
                    items = encoding_tools.decode(line)
                    cmd = items["command"]
                    self.log.debug(f"Trying to execute cmd {cmd}")
                    if cmd not in self.dispatch_dict:
                        self.log.error(f"Command '{line}' unknown")
                        # CODE=2 in this case means "Unsupported command."
                        response = ResponseCode.UNSUPPORTED_COMMAND
                        timeout = -1
                    else:
                        func = self.dispatch_dict[cmd]
                        kwargs = items["parameters"]
                        if cmd[:6] == "status":
                            # the status commands take care of sending a reply
                            # themselves
                            send_response = False
                        if cmd == "stopAz" or cmd == "stopEl":
                            timeout = self.short_timeout
                        await func(**kwargs)
                except (TypeError, RuntimeError):
                    self.log.exception(f"Command '{line}' failed")
                    # CODE=3 in this case means "Missing or incorrect
                    # parameter(s)."
                    response = ResponseCode.INCORRECT_PARAMETER
                    timeout = -1
                if send_response:
                    await self.write(response=response, timeout=timeout)

    async def status_amcs(self):
        """Request the status from the AMCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.amcs, LlcName.AMCS)

    async def status_apscs(self):
        """Request the status from the ApSCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.apscs, LlcName.APSCS)

    async def status_lcs(self):
        """Request the status from the LCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.lcs, LlcName.LCS)

    async def status_lwscs(self):
        """Request the status from the LWSCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.lwscs, LlcName.LWSCS)

    async def status_moncs(self):
        """Request the status from the MonCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.moncs, LlcName.MONCS)

    async def status_thcs(self):
        """Request the status from the ThCS lower level component and write it
        in reply.
        """
        await self.request_and_send_status(self.thcs, LlcName.THCS)

    async def request_and_send_status(self, llc, llc_name):
        """Request the status of the given Lower Level Component and write it
        to the requester.

        Parameters
        ----------
        llc: mock_llc_statuses
            The Lower Level Component to request the status for.
        llc_name: LlcName
            The name of the Lower Level Component.
        """
        self.log.debug("Determining current TAI.")
        await self.determine_current_tai()
        self.log.debug(f"Requesting status for LLC {llc_name}")
        await llc.determine_status(self.current_tai)
        state = {llc_name.value: llc.llc_status}
        await self.write(response=ResponseCode.OK, **state)

    async def determine_current_tai(self):
        """Determine the current TAI time.

        This is done in a separate method so a mock method can replace it in
        unit tests.
        """
        self.current_tai = salobj.current_tai()

    async def move_az(self, position, velocity):
        """Move the dome.

        Parameters
        ----------
        position: `float`
            Desired azimuth, in radians, in range [0, 2 pi)
        velocity: `float`
            The velocity, in deg/sec, to start crawling at once the position
            has been reached.
        """
        self.log.info(
            f"Received command 'moveAz' with arguments position={position} and velocity={velocity}"
        )

        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        await self.amcs.moveAz(position, velocity)

    async def move_el(self, position):
        """Move the light and wind screen.

        Parameters
        ----------
        position: `float`
            Desired elevation, in radians, in range [0, pi/2)
        """
        self.log.info(f"Received command 'moveEl' with argument position={position}")

        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        await self.lwscs.moveEl(position)

    async def stop_az(self):
        """Stop all dome motion.
        """
        self.log.info("Received command 'stopAz'")
        await self.amcs.stopAz()

    async def stop_el(self):
        """Stop all light and wind screen motion.
        """
        self.log.info("Received command 'stopEl'")
        await self.lwscs.stopEl()

    async def stop_llc(self):
        """Move all lower level components.
        """
        await self.stop_az()
        await self.stop_el()
        await self.stop_shutter()
        await self.stop_louvers()

    async def crawl_az(self, velocity):
        """Crawl the dome.

        Parameters
        ----------
        velocity: `float`
            The velocity, in deg/sec, to crawl at.
        """
        self.log.debug(f"Received command 'crawlAz' with argument velocity={velocity}")

        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        await self.amcs.crawlAz(velocity)

    async def crawl_el(self, velocity):
        """Crawl the light and wind screen.

        Parameters
        ----------
        velocity: `float`
            The velocity, in deg/sec, to crawl at.
        """
        self.log.info(f"Received command 'crawlEl' with argument velocity={velocity}")

        # No conversion from radians to degrees needed since both the commands
        # and the mock az controller use radians.
        await self.lwscs.crawlEl(velocity)

    async def set_louvers(self, position):
        """Set the positions of the louvers.

        Parameters
        ----------
        position: array of float
            An array of positions, in percentage with 0 meaning closed and 100
            fully open, for each louver. A position of -1 means "do not move".
        """
        self.log.info(
            f"Received command 'setLouvers' with argument position={position}"
        )
        await self.lcs.setLouvers(position)

    async def close_louvers(self):
        """Close all louvers.
        """
        self.log.info("Received command 'closeLouvers'")
        await self.lcs.closeLouvers()

    async def stop_louvers(self):
        """Stop the motion of all louvers.
        """
        self.log.info("Received command 'stopLouvers'")
        await self.lcs.stopLouvers()

    async def open_shutter(self):
        """Open the shutter.
        """
        self.log.info("Received command 'openShutter'")
        await self.apscs.openShutter()

    async def close_shutter(self):
        """Close the shutter.
        """
        self.log.info("Received command 'closeShutter'")
        await self.apscs.closeShutter()

    async def stop_shutter(self):
        """Stop the motion of the shutter.
        """
        self.log.info("Received command 'stopShutter'")
        await self.apscs.stopShutter()

    async def config(self, system, settings):
        """Configure the lower level components.

        Parameters
        ----------
        system: `str`
            The name of the system to configure.
        settings: `list` of `dict`
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
        self.log.info(
            f"Received command 'config' with arguments system={system} and settings={settings}"
        )
        if system == LlcName.AMCS.value:
            # DM-26653: The structure of the settings variable has changed so
            # we need slightly more complex code here. For info about the new
            # structure, see the project docs at
            # https://ts-dome.lsst.io/protocols.html#configuration-protocol
            for field in settings:
                if field['target'] in ("jmax", "amax", "vmax"):
                    # DM-25758: All param values are passed on as arrays so in
                    # these cases we need to extract the only value in the
                    # array.
                    setattr(self.amcs.amcs_limits, field['target'], field['setting'][0])
        elif system == LlcName.LWSCS.value:
            for field in settings:
                if field['target'] in ("jmax", "amax", "vmax"):
                    # DM-25758: All param values are passed on as arrays so in
                    # these cases we need to extract the only value in the
                    # array.
                    setattr(self.lwscs.lwscs_limits, field['target'], field['setting'][0])
        else:
            raise KeyError(f"Unknown system {system}.")

    async def park(self):
        """Park the dome.
        """
        self.log.info("Received command 'park'")
        await self.amcs.park()

    async def set_temperature(self, temperature):
        """Set the preferred temperature in the dome.

        Parameters
        ----------
        temperature: `float`
            The temperature, in degrees Celsius, to set.
        """
        self.log.info(
            f"Received command 'setTemperature' with argument temperature={temperature}"
        )
        await self.thcs.setTemperature(temperature)

    async def inflate(self, action):
        """Inflate or deflate the inflatable seal.

        Parameters
        ----------
        action: `str`
            ON means inflate and OFF deflate the inflatable seal.
        """
        self.log.info(f"Received command 'inflate' with argument action={action}")
        await self.amcs.inflate(action)

    async def fans(self, action):
        """Enable or disable the fans in the dome.

        Parameters
        ----------
        action: `str`
            ON means fans on and OFF fans off.
        """
        self.log.info(f"Received command 'fans' with argument action={action}")
        await self.amcs.fans(action)


async def main():
    """Main method that gets executed in stand alone mode.
    """
    logging.info("main method")
    # An arbitrarily chosen port. Nothing special about it.
    port = 5000
    logging.info("Constructing mock controller.")
    mock_ctrl = MockDomeController(port=port)
    logging.info("Starting mock controller.")
    await mock_ctrl.start(keep_running=True)


if __name__ == "__main__":
    logging.info("main")
    loop = asyncio.get_event_loop()
    try:
        logging.info("Calling main method")
        loop.run_until_complete(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass

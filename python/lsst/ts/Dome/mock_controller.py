__all__ = ["MockDomeController"]

import asyncio
import logging

from .llc_name import LlcName
from lsst.ts import salobj
from lsst.ts.Dome import encoding_tools
from . import mock_llc_statuses
from .response_code import ResponseCode


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
            "crawlAz": self.crawlAz,
            "crawlEl": self.crawlEl,
            "setLouver": self.setLouver,
            "closeLouvers": self.closeLouvers,
            "stopLouvers": self.stopLouvers,
            "openShutter": self.openShutter,
            "closeShutter": self.closeShutter,
            "stopShutter": self.stopShutter,
            "config": self.config,
            "park": self.park,
            "setTemperature": self.setTemperature,
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

        Start the command loop and make sure to keep running when instructed to do so.

        Parameters
        ----------
        keep_running : bool
            Used for command line testing and should generally be left to False.
        """
        self.log.info("Start called")
        self._server = await asyncio.start_server(
            self.cmd_loop, host="127.0.0.1", port=self.port
        )
        # Request the assigned port from the server so the code starting the mock controller can use it to
        # connect.
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
            self.log.info("Waiting for next command.")
            timeout = self.long_timeout

            line = None
            try:
                line = await reader.readuntil(b"\r\n")
                line = line.decode().strip()
                self.log.info(f"Read command line: {line!r}")
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
                        kwargs = {}
                        if cmd == "config":
                            # it is unclear beforehand which config parameters are being sent so just
                            # remove the "config" key and pass the rest on.
                            kwargs = {x: items[x] for x in items if x not in "config"}
                        else:
                            # all other commands should send the "parameters" key. If it doesn't exist then
                            # a KeyError will be raised which gets caught a few lines down.
                            kwargs = items["parameters"]
                        if cmd[:6] == "status":
                            # the status commands take care of sending a reply themselves
                            send_response = False
                        if cmd == "stopAz" or cmd == "stopEl":
                            timeout = self.short_timeout
                        await func(**kwargs)
                except (KeyError, RuntimeError):
                    self.log.error(f"Command '{line}' failed")
                    # CODE=3 in this case means "Missing or incorrect parameter(s)."
                    response = ResponseCode.INCORRECT_PARAMETER
                    timeout = -1
                if send_response:
                    await self.write(response=response, timeout=timeout)

    async def status_amcs(self):
        """Request the status from the AMCS lower level component and write it in reply.
        """
        await self.request_and_send_status(self.amcs, LlcName.AMCS)

    async def status_apscs(self):
        """Request the status from the ApSCS lower level component and write it in reply.
        """
        await self.request_and_send_status(self.apscs, LlcName.APSCS)

    async def status_lcs(self):
        """Request the status from the LCS lower level component and write it in reply.
        """
        await self.request_and_send_status(self.lcs, LlcName.LCS)

    async def status_lwscs(self):
        """Request the status from the LWSCS lower level component and write it in reply.
        """
        await self.request_and_send_status(self.lwscs, LlcName.LWSCS)

    async def status_moncs(self):
        """Request the status from the MonCS lower level component and write it in reply.
        """
        await self.request_and_send_status(self.moncs, LlcName.MONCS)

    async def status_thcs(self):
        """Request the status from the ThCS lower level component and write it in reply.
        """
        await self.request_and_send_status(self.thcs, LlcName.THCS)

    async def request_and_send_status(self, llc, llc_name):
        """Request the status of the given Lower Level Component and write it to the requester.

        Parameters
        ----------
        llc: mock_llc_statuses
            The Lower Level Component to request the status for.
        llc_name: LlcName
            The name of the Lower Level Component.
        """
        await llc.determine_status(self.current_tai)
        state = {llc_name.value: llc.llc_status}
        await self.write(response=ResponseCode.OK, **state)

    async def determine_current_tai(self):
        """Determine the time difference since the previous call.
        """
        self.current_tai = salobj.current_tai()

    async def move_az(self, **kwargs):
        """Move the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "azimuth" with a
            float value between 0 and 2pi and the key "azRate" with a float value where positive means
            towards increasing azimuth and negative towards decreasing azimuth.
        """
        self.log.debug(f"Received command 'moveAz' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use radians.
        await self.amcs.moveAz(
            azimuth=float(kwargs["azimuth"]), velocity=float(kwargs["azRate"])
        )

    async def move_el(self, **kwargs):
        """Move the light and wind screen.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "elevation" with a
            float value between 0 and pi/2.
        """
        self.log.debug(f"Received command 'moveEl' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use radians.
        await self.lwscs.moveEl(elevation=float(kwargs["elevation"]))

    async def stop_az(self):
        """Stop all dome motion.
        """
        self.log.debug("Received command 'stopAz'")
        await self.amcs.stopAz()

    async def stop_el(self):
        """Stop all light and wind screen motion.
        """
        self.log.debug("Received command 'stopEl'")
        await self.lwscs.stopEl()

    async def stop_llc(self):
        """Move all lower level components.
        """
        await self.stop_az()
        await self.stop_el()
        await self.stopShutter()
        await self.stopLouvers()

    async def crawlAz(self, **kwargs):
        """Crawl the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "azRate" with a
            float value where positive means towards increasing azimuth and negative towards decreasing
            azimuth.
        """
        self.log.debug(f"Received command 'crawlAz' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use radians.
        await self.amcs.crawlAz(velocity=float(kwargs["azRate"]))

    async def crawlEl(self, **kwargs):
        """Crawl the light and wind screen.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "elRate" with a
            float value where positive means towards increasing elevation and negative towards decreasing
            elevation.
        """
        self.log.info(f"Received command 'crawlEl' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use radians.
        await self.lwscs.crawlEl(velocity=float(kwargs["elRate"]))

    async def setLouver(self, **kwargs):
        """Set the position of a louver.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "id" with an int
            value and the key "position" with a float value.
        """
        self.log.info(f"Received command 'setLouver' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use radians.
        await self.lcs.setLouver(
            louver_id=int(kwargs["id"]), position=float(kwargs["position"])
        )

    async def closeLouvers(self):
        """Close all louvers.
        """
        self.log.info(f"Received command 'closeLouvers'")
        await self.lcs.closeLouvers()

    async def stopLouvers(self):
        """Stop the motion of all louvers.
        """
        self.log.info(f"Received command 'stopLouvers'")
        await self.lcs.stopLouvers()

    async def openShutter(self):
        """Open the shutter.
        """
        self.log.info(f"Received command 'openShutter'")
        await self.apscs.openShutter()

    async def closeShutter(self):
        """Close the shutter.
        """
        self.log.info(f"Received command 'closeShutter'")
        await self.apscs.closeShutter()

    async def stopShutter(self):
        """Stop the motion of the shutter.
        """
        self.log.info(f"Received command 'stopShutter'")
        await self.apscs.stopShutter()

    async def config(self, **kwargs):
        """Configure the lower level components.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain keys for all lower level
            components to be configured with values that are dicts with keys for all the parameters that
            need to be configured. The structure is::

                "AMCS":
                    "jmax"
                    "amax"
                    "vmax"
                "LWSCS":
                    "jmax"
                    "amax"
                    "vmax"

            It is assumed that the values of the configuration parameters are validated to lie within the
            limits before being passed on to this function.
            It is assumed that all configuration parameters are present and that their values represent the
            value to set even unchanged.
        """
        self.log.info(f"Received command 'config' with arguments {kwargs}")
        amcs_config = kwargs.get(LlcName.AMCS.value)
        if amcs_config:
            for field in ("jmax", "amax", "vmax"):
                if field in amcs_config:
                    setattr(self.amcs.amcs_limits, field, amcs_config[field])
        lwscs_config = kwargs.get(LlcName.LWSCS.value)
        if lwscs_config:
            for field in ("jmax", "amax", "vmax"):
                if field in lwscs_config:
                    setattr(self.lwscs.lwscs_limits, field, lwscs_config[field])

    async def park(self):
        """Park the dome.
        """
        self.log.info(f"Received command 'park'")
        await self.amcs.park()

    async def setTemperature(self, **kwargs):
        """Set the preferred temperature in the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "temperature" with a
            float value.
        """
        self.log.info(f"Received command 'setTemperature' with arguments {kwargs}")
        await self.thcs.setTemperature(temperature=float(kwargs["temperature"]))

    async def inflate(self, **kwargs):
        """Inflate or deflate the inflatable seal.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            boolean value.
        """
        self.log.info(f"Received command 'inflate' with arguments {kwargs}")
        await self.amcs.inflate(action=kwargs["action"])

    async def fans(self, **kwargs):
        """Enable or disable the fans in the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            boolean value.
        """
        self.log.info(f"Received command 'fans' with arguments {kwargs}")
        await self.amcs.fans(action=kwargs["action"])


async def main():
    """Main method that gets executed in stand alone mode.
    """
    # An arbitrarily chosen port. Nothing special about it.
    port = 5000
    mock_ctrl = MockDomeController(port=port)
    logging.info("main")
    await mock_ctrl.start(keep_running=True)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass

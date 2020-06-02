import asyncio
import logging

import yaml

from lsst.ts import salobj
from . import mock_llc_statuses
from .error_code import ErrorCode
from .llc_name import LlcName


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
            "status": self.status,
        }
        # Name of a command to report as failed once, the next time it is seen,
        # or None if no failures. Used to test CSC handling of failed commands.
        self.fail_command = None
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

    async def write(self, st):
        """Write the string appended with a newline character.

        Parameters
        ----------
        st: `str`
            The string to write.
        """
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
        await self.write(f"ERROR:\n CODE: {code.value}\n")

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
            print_ok = True
            line = None
            try:
                line = await reader.readuntil(b"\r\n")
                line = line.decode().strip()
                self.log.info(f"Read command line: {line!r}")
            except asyncio.IncompleteReadError:
                return
            if line:
                try:
                    outputs = None
                    # demarshall the line into a dict of Python objects.
                    items = yaml.safe_load(line)
                    cmd = next(iter(items))
                    self.log.debug(f"Trying to execute cmd {cmd}")
                    if cmd not in self.dispatch_dict:
                        self.log.error(f"Command '{line}' unknown")
                        # CODE=2 in this case means "Unsupported command."
                        await self.write_error(ErrorCode.UNSUPPORTED_COMMAND)
                        print_ok = False
                    elif cmd == self.fail_command:
                        self.fail_command = None
                        outputs = [f"Command '{cmd}' failed by request"]
                    else:
                        func = self.dispatch_dict[cmd]
                        kwargs = {}
                        args = items[cmd]
                        if args is not None:
                            for arg in args:
                                kwargs[arg] = args[arg]
                        outputs = await func(**kwargs)
                        if cmd == "status":
                            print_ok = False
                        if cmd == "stopAz" or cmd == "stopEl":
                            timeout = self.short_timeout
                    if outputs:
                        for msg in outputs:
                            await self.write(msg)
                except (KeyError, RuntimeError):
                    self.log.error(f"Command '{line}' failed")
                    # CODE=3 in this case means "Missing or incorrect parameter(s)."
                    await self.write_error(ErrorCode.INCORRECT_PARAMETER)
                    print_ok = False
                if print_ok:
                    await self.write(f"OK:\n Timeout: {timeout}\n")

    async def status(self):
        """Request the status from the lower level components and write them in reply.
        """
        self.log.debug("Received command 'status'")
        await self.determine_current_tai()
        await self.determine_statuses()
        amcs_state = self.amcs.llc_status
        apcs_state = self.apscs.llc_status
        lcs_state = self.lcs.llc_status
        lwscs_state = self.lwscs.llc_status
        moncs_state = self.moncs.llc_status
        thcs_state = self.thcs.llc_status
        reply = {
            LlcName.AMCS.value: amcs_state,
            LlcName.APSCS.value: apcs_state,
            LlcName.LCS.value: lcs_state,
            LlcName.LWSCS.value: lwscs_state,
            LlcName.MONCS.value: moncs_state,
            LlcName.THCS.value: thcs_state,
        }
        data = yaml.safe_dump(reply, default_flow_style=None)
        await self.write("OK:\n" + data)

    async def determine_statuses(self):
        """Determine the status of the lower level components.
        """
        self.log.debug(f"self.current_tai = {self.current_tai}")
        await self.amcs.determine_status(self.current_tai)
        await self.apscs.determine_status(self.current_tai)
        await self.lcs.determine_status(self.current_tai)
        await self.lwscs.determine_status(self.current_tai)
        await self.moncs.determine_status(self.current_tai)
        await self.thcs.determine_status(self.current_tai)

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
                    setattr(self, field, amcs_config[field])
        lwscs_config = kwargs.get(LlcName.LWSCS.value)
        if lwscs_config:
            for field in ("jmax", "amax", "vmax"):
                if field in lwscs_config:
                    setattr(self, field, lwscs_config[field])

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

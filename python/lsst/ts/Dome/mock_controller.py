import asyncio
import logging
import yaml

from .mock_llc_statuses.amcs_status import MockAmcsStatus
from .mock_llc_statuses.apscs_status import MockApscsStatus
from .mock_llc_statuses.lcs_status import MockLcsStatus
from .mock_llc_statuses.lwscs_status import MockLwscsStatus
from .mock_llc_statuses.moncs_status import MockMoncsStatus
from .mock_llc_statuses.thcs_status import MockThcsStatus


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
        self.status_task = None
        self.period = 0.1

        # Variables to hold the status of the lower level components.
        self.amcs = MockAmcsStatus(period=self.period)
        self.apscs = MockApscsStatus()
        self.lcs = MockLcsStatus()
        self.lwscs = MockLwscsStatus(period=self.period)
        self.moncs = MockMoncsStatus()
        self.thcs = MockThcsStatus()

        self.do_cmd_loop = True
        self.do_status_loop = True

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
        self.log.info("Starting LLCs")
        self.status_task = asyncio.create_task(self.run_status_task())

        if keep_running:
            await self._server.serve_forever()

    async def stop(self):
        """Stop the mock lower level components and the TCP/IP server.
        """
        await self.stop_status_task()
        self.do_cmd_loop = False

        if self._server is None:
            return

        server = self._server
        self._server = None
        self.log.info("Closing server")
        server.close()
        self.log.info("Done closing")

    async def run_status_task(self):
        """Run a loop every "period" seconds to determine the status of the lower level components.
        """
        while self.do_status_loop:
            await self.amcs.determine_status()
            await self.apscs.determine_status()
            await self.lcs.determine_status()
            await self.lwscs.determine_status()
            await self.moncs.determine_status()
            await self.thcs.determine_status()
            await asyncio.sleep(self.period)

    async def stop_status_task(self):
        """Stop the status task loop.
        """
        self.do_status_loop = False
        self.status_task.cancel()

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
        while self.do_cmd_loop:
            self.log.info("Waiting for next command.")
            timeout = 20
            print_ok = True
            line = None
            try:
                line = await reader.readuntil(b"\r\n")
                line = line.decode().strip()
                self.log.debug(f"Read command line: {line!r}")
            except asyncio.IncompleteReadError:
                pass
            if line:
                try:
                    outputs = None
                    # demarshall the line into a dict of Python objects.
                    items = yaml.safe_load(line)
                    cmd = next(iter(items))
                    self.log.debug(f"Trying to execute cmd {cmd}")
                    if cmd not in self.dispatch_dict:
                        self.log.exception(f"Command '{line}' unknown")
                        # CODE=2 in this case means "Unsupported command."
                        await self.write("ERROR:\n CODE: 2\n")
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
                            timeout = 2
                    if outputs:
                        for msg in outputs:
                            await self.write(msg)
                except (KeyError, RuntimeError):
                    self.log.exception(f"Command '{line}' failed")
                    # CODE=3 in this case means "Missing or incorrect parameter(s)."
                    await self.write("ERROR:\n CODE: 3\n")
                    print_ok = False
                if print_ok:
                    await self.write(f"OK:\n Timeout: {timeout}\n")

    async def status(self):
        """Request the status from the lower level components and write them in reply.
        """
        self.log.debug("Received command 'status'")
        amcs_state = self.amcs.llc_status
        apcs_state = self.apscs.llc_status
        lcs_state = self.lcs.llc_status
        lwscs_state = self.lwscs.llc_status
        moncs_state = self.moncs.llc_status
        thcs_state = self.thcs.llc_status
        reply = {
            "AMCS": amcs_state,
            "ApSCS": apcs_state,
            "LCS": lcs_state,
            "LWSCS": lwscs_state,
            "ThCS": thcs_state,
            "MonCS": moncs_state,
        }
        data = yaml.safe_dump(reply, default_flow_style=None)
        await self.write("OK:\n" + data)

    async def move_az(self, **kwargs):
        """Mock moving the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "azimuth" with a
            float value.
        """
        self.log.debug(f"Received command 'moveAz' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use degrees.
        await self.amcs.moveAz(azimuth=float(kwargs["azimuth"]))

    async def move_el(self, **kwargs):
        """Mock moving the light and wind screen.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "elevation" with a
            float value.
        """
        self.log.debug(f"Received command 'moveEl' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use degrees.
        await self.lwscs.moveEl(elevation=float(kwargs["elevation"]))

    async def stop_az(self):
        """Mock stopping all dome motion.
        """
        self.log.debug("Received command 'stopAz'")
        await self.amcs.stopAz()

    async def stop_el(self):
        """Mock stopping all light and wind screen motion.
        """
        self.log.debug("Received command 'stopEl'")
        await self.lwscs.stopEl()

    async def stop_llc(self):
        """Stop moving all lower level components.
        """
        await self.stop_az()
        await self.stop_el()
        await self.stopShutter()
        await self.stopLouvers()

    async def crawlAz(self, **kwargs):
        """Mock crawling the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "dirMotion" with a
            string value (CW or CCW) and the key "azRate" with a float value.
        """
        self.log.debug(f"Received command 'crawlAz' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use degrees.
        await self.amcs.crawlAz(
            direction=kwargs["dirMotion"], velocity=float(kwargs["azRate"])
        )

    async def crawlEl(self, **kwargs):
        """Mock crawling the light and wind screen.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "dirMotion" with a
            string value (UP or DOWN) and the key "elRate" with a float value.
        """
        self.log.info(f"Received command 'crawlEl' with arguments {kwargs}")
        await self.lwscs.crawlEl(
            direction=kwargs["dirMotion"], velocity=float(kwargs["elRate"])
        )

    async def setLouver(self, **kwargs):
        """Mock setting the position of a louver.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "id" with an int
            value and the key "position" with a float value.
        """
        self.log.info(f"Received command 'setLouver' with arguments {kwargs}")
        await self.lcs.setLouver(
            louver_id=int(kwargs["id"]), position=int(kwargs["position"])
        )

    async def closeLouvers(self):
        """Mock closing all louvers.
        """
        self.log.info(f"Received command 'closeLouvers'")
        await self.lcs.closeLouvers()

    async def stopLouvers(self):
        """Mock stopping the motion of all louvers.
        """
        self.log.info(f"Received command 'stopLouvers'")
        await self.lcs.stopLouvers()

    async def openShutter(self):
        """Mock opening the shutter.
        """
        self.log.info(f"Received command 'openShutter'")
        await self.apscs.openShutter()

    async def closeShutter(self):
        """Mock closing the shutter.
        """
        self.log.info(f"Received command 'closeShutter'")
        await self.apscs.closeShutter()

    async def stopShutter(self):
        """Mock stopping the motion of the shutter.
        """
        self.log.info(f"Received command 'stopShutter'")
        await self.apscs.stopShutter()

    async def config(self, **kwargs):
        """Mock configure the lower level components.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain keys for all lower level
            components to be configured with values that are dicts with keys for all the parameters that
            need to be configured. The structure is
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
        """
        self.log.info(f"Received command 'config' with arguments {kwargs}")
        if kwargs["AMCS"]:
            amcs_config = kwargs["AMCS"]
            if amcs_config["jmax"]:
                self.amcs.jmax = amcs_config["jmax"]
            if amcs_config["amax"]:
                self.amcs.amax = amcs_config["amax"]
            if amcs_config["vmax"]:
                self.amcs.vmax = amcs_config["vmax"]
        if kwargs["LWSCS"]:
            lwscs_config = kwargs["LWSCS"]
            if lwscs_config["jmax"]:
                self.lwscs.jmax = lwscs_config["jmax"]
            if lwscs_config["amax"]:
                self.lwscs.amax = lwscs_config["amax"]
            if lwscs_config["vmax"]:
                self.lwscs.vmax = lwscs_config["vmax"]

    async def park(self):
        """Mock parking the dome.
        """
        self.log.info(f"Received command 'park'")
        await self.amcs.park()

    async def setTemperature(self, **kwargs):
        """Mock setting the preferred temperature in the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "temperature" with a
            float value.
        """
        self.log.info(f"Received command 'setTemperature' with arguments {kwargs}")
        await self.thcs.setTemperature(temperature=float(kwargs["temperature"]))

    async def fans(self, **kwargs):
        """Mock switching on or off the fans in the dome.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            string value (ON or OFF).
        """
        self.log.info(f"Received command 'fans' with arguments {kwargs}")

    async def inflate(self, **kwargs):
        """Mock inflating or deflating the inflatable seal.

        Parameters
        ----------
        kwargs: `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            string value (ON or OFF).
        """
        self.log.info(f"Received command 'inflate' with arguments {kwargs}")


async def main():
    """Main method that gets executed in stand alone mode.
    """
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

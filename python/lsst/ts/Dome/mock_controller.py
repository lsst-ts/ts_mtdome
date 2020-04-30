import asyncio
import logging
import yaml

from .mock_llc_statuses.mock_azcs_status import MockAzcsStatus
from .mock_llc_statuses.mock_lwscs_status import MockLwscsStatus


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
        self.do_cmd_loop = True
        self.log = logging.getLogger("MockDomeController")
        # Dict of command: (has_argument, function).
        # The function is called with:
        # * No arguments, if `has_argument` False.
        # * The argument as a string, if `has_argument` is True.
        self.dispatch_dict = {
            "status": self.status,
            "moveAz": self.move_az,
            "moveEl": self.move_el,
            "stopAz": self.stop_az,
            "stopEl": self.stop_el,
            "stop": self.stop,
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
            "quit": self.quit,
        }
        # Name of a command to report as failed once, the next time it is seen,
        # or None if no failures. Used to test CSC handling of failed commands.
        self.fail_command = None
        # Variables to hold the status of the lower level components.
        self.az = MockAzcsStatus()
        self.az_motion_task = None
        self.lws = MockLwscsStatus()
        self.lws_motion_task = None

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
        self.az_motion_task = asyncio.create_task(self.az.start())
        self.lws_motion_task = asyncio.create_task(self.lws.start())

        if keep_running:
            await self._server.serve_forever()

    async def stop(self):
        """Stop the mock lower level components and the TCP/IP server.
        """
        self.az_motion_task.cancel()
        self.lws_motion_task.cancel()
        self.do_cmd_loop = False

        if self._server is None:
            return

        server = self._server
        self._server = None
        self.log.info("Closing server")
        server.close()
        self.log.info("Done closing")

    async def write(self, st):
        """Write the string st appended with a newline character
        """
        self._writer.write(st.encode() + b"\r\n")
        self.log.debug(st)
        await self._writer.drain()

    async def cmd_loop(self, reader, writer):
        """Execute commands and output replies."""
        self.log.info("The cmd_loop begins")
        self._writer = writer
        while self.do_cmd_loop:
            self.log.info("cmd_loop")
            timeout = 20
            print_ok = True
            line = None
            try:
                line = await reader.readuntil(b"\r\n")
                line = line.decode().strip()
                self.log.info(f"Read command line: {line!r}")
            except asyncio.IncompleteReadError:
                pass
            if line:
                try:
                    outputs = None
                    # demarshall the line into a dict of Python objects.
                    items = yaml.safe_load(line)
                    cmd = next(iter(items))
                    self.log.info(f"Trying to execute cmd {cmd}")
                    if cmd not in self.dispatch_dict:
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
                        if cmd == "status" or cmd == "quit":
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
        self.log.info("Received command 'status'")
        amcs_state = self.az.amcs_state
        apcs_state = "TBD"
        lcs_state = "TBD"
        lwscs_state = self.lws.lwscs_state
        thcs_state = "TBD"
        moncs_state = "TBD"
        reply = {
            "AMCS": amcs_state,
            "ApCS": apcs_state,
            "LCS": lcs_state,
            "LWSCS": lwscs_state,
            "ThCS": thcs_state,
            "MonCS": moncs_state,
        }
        data = yaml.safe_dump(reply, default_flow_style=None)
        await self.write("OK:\n" + data)

    async def move_az(self, **kwargs):
        self.log.info(f"Received command 'moveAz' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use degrees.
        await self.az.moveAz(azimuth=float(kwargs["azimuth"]))

    async def move_el(self, **kwargs):
        self.log.info(f"Received command 'moveEl' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use degrees.
        await self.lws.moveEl(elevation=float(kwargs["elevation"]))

    async def stop_az(self):
        self.log.info("Received command 'stopAz'")
        self.az.motion = "Stopped"

    async def stop_el(self):
        self.log.info("Received command 'stopEl'")
        self.lws.motion = "Stopped"

    async def crawlAz(self, **kwargs):
        self.log.info(f"Received command 'crawlAz' with arguments {kwargs}")

        # No conversion from radians to degrees needed since both the commands and the mock az controller
        # use degrees.
        await self.az.crawlAz(
            direction=kwargs["dirMotion"], velocity=float(kwargs["azRate"])
        )

    async def crawlEl(self, **kwargs):
        self.log.info(f"Received command 'crawlEl' with arguments {kwargs}")
        await self.lws.crawlEl(
            direction=kwargs["dirMotion"], velocity=float(kwargs["elRate"])
        )

    async def setLouver(self, **kwargs):
        self.log.info(f"Received command 'setLouver' with arguments {kwargs}")

    async def closeLouvers(self):
        self.log.info(f"Received command 'closeLouvers'")

    async def stopLouvers(self):
        self.log.info(f"Received command 'stopLouvers'")

    async def openShutter(self):
        self.log.info(f"Received command 'openShutter'")

    async def closeShutter(self):
        self.log.info(f"Received command 'closeShutter'")

    async def stopShutter(self):
        self.log.info(f"Received command 'stopShutter'")

    async def config(self, **kwargs):
        self.log.info(f"Received command 'config' with arguments {kwargs}")
        if kwargs["AMCS"]:
            amcs_config = kwargs["AMCS"]
            if amcs_config["jmax"]:
                self.az.jmax = amcs_config["jmax"]
            if amcs_config["amax"]:
                self.az.amax = amcs_config["amax"]
            if amcs_config["vmax"]:
                self.az.vmax = amcs_config["vmax"]
        if kwargs["LWSCS"]:
            lwscs_config = kwargs["LWSCS"]
            if lwscs_config["jmax"]:
                self.lws.jmax = lwscs_config["jmax"]
            if lwscs_config["amax"]:
                self.lws.amax = lwscs_config["amax"]
            if lwscs_config["vmax"]:
                self.lws.vmax = lwscs_config["vmax"]

    async def park(self):
        self.log.info(f"Received command 'park'")

    async def setTemperature(self, **kwargs):
        self.log.info(f"Received command 'setTemperature' with arguments {kwargs}")

    async def fans(self, **kwargs):
        self.log.info(f"Received command 'fans' with arguments {kwargs}")

    async def inflate(self, **kwargs):
        self.log.info(f"Received command 'inflate' with arguments {kwargs}")

    async def quit(self):
        self.log.info("Received command 'quit'")
        await self.stop()


async def main():
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

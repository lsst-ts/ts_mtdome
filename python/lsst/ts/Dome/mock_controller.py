import asyncio
import logging
import yaml

logging.basicConfig(level=logging.INFO)


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
            "status": self.status,
            "moveAz": self.move_az,
            "moveEl": self.move_el,
            "stopAz": self.stop_az,
            "stopEl": self.stop_el,
            "quit": self.quit,
        }
        # Name of a command to report as failed once, the next time it is seen,
        # or None if no failures. Used to test CSC handling of failed commands.
        self.fail_command = None

        # Variables to hold the status of the lower level components.
        self.az_current_azimuth = 0
        self.az_motion_azimuth = 0
        self.az_motion = "Stopped"
        self.el_current_elevation = 0
        self.el_motion_elevation = 0
        self.el_motion = "Stopped"

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
        if keep_running:
            await self._server.serve_forever()

    async def stop(self):
        """Stop the TCP/IP server.
        """
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
        self.log.info(st)
        await self._writer.drain()

    async def cmd_loop(self, reader, writer):
        """Execute commands and output replies."""
        self.log.info("The cmd_loop begins")
        self._writer = writer
        await self.status()
        while True:
            print_ok = True
            line = await reader.readuntil(b"\r\n")
            line = line.decode().strip()
            self.log.info(f"Read command line: {line!r}")
            timeout = 20
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
        amcs_state = self.determine_az_state()
        apcs_state = self.determine_el_state()
        lcs_state = "TBD"
        lwcs_state = "TBD"
        thcs_state = "TBD"
        moncs_state = "TBD"
        reply = {
            "AMCS": amcs_state,
            "ApCS": apcs_state,
            "LCS": lcs_state,
            "LWCS": lwcs_state,
            "ThCS": thcs_state,
            "MonCS": moncs_state,
        }
        data = yaml.safe_dump(reply, default_flow_style=None)
        await self.write("OK:\n" + data)

    def determine_az_state(self):
        az_motion = "Stopped"
        self.log.info(f"self.az_motion = {self.az_motion}")
        if self.az_motion != "Stopped":
            az_motion = self.az_motion + " to azimuth " + str(self.az_motion_azimuth)
            if self.az_current_azimuth < self.az_motion_azimuth:
                self.az_current_azimuth = self.az_current_azimuth + 5
                if self.az_current_azimuth >= self.az_motion_azimuth:
                    self.az_current_azimuth = self.az_motion_azimuth
                    self.az_motion = "Stopped"
            else:
                self.az_current_azimuth = self.az_current_azimuth - 5
                if self.az_current_azimuth <= self.az_motion_azimuth:
                    self.az_current_azimuth = self.az_motion_azimuth
                    self.az_motion = "Stopped"
        amcs_state = {
            "status": az_motion,
            "positionError": 0.0,
            "positionActual": self.az_current_azimuth,
            "positionCmd": 0.0,
            "driveTorqueActual": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveTorqueError": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveTorqueCmd": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveCurrentActual": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveTempActual": [20.0, 20.0, 20.0, 20.0, 20.0],
            "encoderHeadRaw": [0.0, 0.0, 0.0, 0.0, 0.0],
            "encoderHeadCalibrated": [0.0, 0.0, 0.0, 0.0, 0.0],
            "resolverRaw": [0.0, 0.0, 0.0, 0.0, 0.0],
            "resolverCalibrated": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
        return amcs_state

    def determine_el_state(self):
        el_motion = "Stopped"
        self.log.info(f"self.el_motion = {self.el_motion}")
        if self.el_motion != "Stopped":
            el_motion = (
                self.el_motion + " to elevation " + str(self.el_motion_elevation)
            )
            if self.el_current_elevation < self.el_motion_elevation:
                self.el_current_elevation = self.el_current_elevation + 5
                if self.el_current_elevation >= self.el_motion_elevation:
                    self.el_current_elevation = self.el_motion_elevation
                    self.el_motion = "Stopped"
            else:
                self.el_current_elevation = self.el_current_elevation - 5
                if self.el_current_elevation <= self.el_motion_elevation:
                    self.el_current_elevation = self.el_motion_elevation
                    self.el_motion = "Stopped"
        apcs_state = {
            "status": el_motion,
            "positionError": 0.0,
            "positionActual": self.el_current_elevation,
            "positionCmd": 0.0,
            "driveTorqueActual": [0.0, 0.0, 0.0, 0.0],
            "driveTorqueError": [0.0, 0.0, 0.0, 0.0],
            "driveTorqueCmd": [0.0, 0.0, 0.0, 0.0],
            "driveCurrentActual": [0.0, 0.0, 0.0, 0.0],
            "driveTempActual": [20.0, 20.0, 20.0, 20.0],
            "resolverHeadRaw": [0.0, 0.0, 0.0, 0.0],
            "resolverHeadCalibrated": [0.0, 0.0, 0.0, 0.0],
            "powerAbsortion": 0.0,
        }
        return apcs_state

    async def move_az(self, **kwargs):
        self.log.info(f"Received command 'moveAz' with arguments {kwargs}")
        self.az_motion_azimuth = float(kwargs["azimuth"])
        self.az_motion = "Moving"

    async def move_el(self, **kwargs):
        self.log.info(f"Received command 'moveEl' with arguments {kwargs}")
        self.el_motion_elevation = float(kwargs["elevation"])
        self.el_motion = "Moving"

    async def stop_az(self):
        self.log.info("Received command 'stopAz'")
        self.az_motion = "Stopped"

    async def stop_el(self):
        self.log.info("Received command 'stopEl'")
        self.el_motion = "Stopped"

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

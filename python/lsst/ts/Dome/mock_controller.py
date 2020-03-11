import asyncio
import logging

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

        self.az_current_position = 0
        self.az_motion_position = 0
        self.az_motion = "Stopped"

    async def start(self):
        """Start the TCP/IP server.

        Set start_task done and start the command loop.
        """
        self.log.info("start called")
        self._server = await asyncio.start_server(
            self.cmd_loop, host="127.0.0.1", port=self.port
        )
        await self._server.serve_forever()

    async def stop(self):
        """Stop the TCP/IP server.
        """
        if self._server is None:
            return

        server = self._server
        self._server = None
        self.log.info("closing server")
        server.close()
        self.log.info("done closing")

    # noinspection PyMethodMayBeStatic
    async def write(self, st):
        """Write the string st appended with a newline character
        """
        st = f"{st}\n"
        self._writer.write(st.encode())
        await self._writer.drain()

    async def cmd_loop(self, reader, writer):
        """Execute commands and output replies."""
        self.log.info("cmd_loop begins")
        self._writer = writer
        await self.status()
        while True:
            print_ok = True
            line = await reader.readline()
            line = line.decode()
            if not line:
                # connection lost; close the writer and exit the loop
                self.log.info("closing the writer")
                writer.close()
                self.log.info("stopping mock controller")
                await self.stop()
                return
            line = line.strip()
            self.log.info(f"read command: {line!r}")
            timeout = 20
            if line:
                try:
                    items = line.split(";")
                    cmd = items[0]
                    if cmd not in self.dispatch_dict:
                        # CODE=2 in this case means "Unsupported command."
                        await self.write("ERROR;CODE=2")
                        print_ok = False
                    if cmd == self.fail_command:
                        self.fail_command = None
                        outputs = [f"Command '{cmd}' failed by request"]
                    else:
                        func = self.dispatch_dict[cmd]
                        kwargs = {}
                        for item in items[1:]:
                            arg = item.split("=")
                            kwargs[arg[0]] = arg[1]
                        outputs = await func(**kwargs)
                        if cmd == "status" or cmd == "quit":
                            print_ok = False
                        if cmd == "stopAz":
                            timeout = 2
                    if outputs:
                        for msg in outputs:
                            await self.write(msg)
                except (KeyError, RuntimeError):
                    self.log.exception(f"command '{line}' failed")
                    # CODE=3 in this case means "Missing or incorrect parameter(s)."
                    await self.write("ERROR;CODE=3")
                    print_ok = False
            if print_ok:
                await self.write(f"OK;Timeout={timeout}")

    async def status(self):
        self.log.info("Received command 'status'")
        az_motion = "Stopped"
        if self.az_motion != "Stopped":
            az_motion = self.az_motion + " to position " + str(self.az_motion_position)
            if self.az_current_position < self.az_motion_position:
                self.az_current_position = self.az_current_position + 5
                if self.az_current_position >= self.az_motion_position:
                    self.az_current_position = self.az_motion_position
                    self.az_motion = "Stopped"
            else:
                self.az_current_position = self.az_current_position - 5
                if self.az_current_position <= self.az_motion_position:
                    self.az_current_position = self.az_motion_position
                    self.az_motion = "Stopped"
        await self.write(
            (
                f"OK;AMCS:{az_motion};positionError=0.0;"
                f"positionActual={self.az_current_position};positionCmd=0.0;"
                + "driveTorqueActual=[0.0,0.0,0.0,0.0,0.0];"
                + "drivecd TorqueError=[0.0,0.0,0.0,0.0,0.0];"
                + "driveTorqueCmd=[0.0,0.0,0.0,0.0,0.0];"
                + "driveCurrentActual=[0.0,0.0,0.0,0.0,0.0];"
                + "driveTempActual=[20.0,20.0,20.0,20.0,20.0];"
                + "encoderHeadRaw=[0.0,0.0,0.0,0.0,0.0];"
                + "encoderHeadCalibrated=[0.0,0.0,0.0,0.0,0.0];"
                + "resolverRaw=[0.0,0.0,0.0,0.0,0.0];"
                + "resolverCalibrated=[0.0,0.0,0.0,0.0,0.0];"
                + "ApCS:TBD;"
                + "LCS:TBD;"
                + "LWCS:TBD;"
                + "ThCS:TBD;"
                + "MonCS:TBD;"
            ),
        )

    async def move_az(self, **kwargs):
        self.log.info(f"Received command 'moveAz' with arguments {kwargs}")
        self.az_motion_position = float(kwargs["position"])
        self.az_motion = "Moving"

    async def move_el(self, **kwargs):
        self.log.info(f"Received command 'moveEl' with arguments {kwargs}")

    async def stop_az(self):
        self.log.info("Received command 'stopAz'")
        self.az_motion = "Stopped"

    async def stop_el(self):
        self.log.info("Received command 'stopEl'")

    async def quit(self):
        self.log.info("Received command 'quit'")
        await self.stop()


async def main():
    port = 5000
    mock_ctrl = MockDomeController(port=port)
    logging.info("main")
    await mock_ctrl.start()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass

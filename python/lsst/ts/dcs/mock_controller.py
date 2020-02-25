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
            self,
            port,
    ):
        self.port = port
        self._server = None
        self.log = logging.getLogger("MockDomeController")
        # Dict of command: (has_argument, function).
        # The function is called with:
        # * No arguments, if `has_argument` False.
        # * The argument as a string, if `has_argument` is True.
        self.dispatch_dict = {
            "status": (False, self.status),
            "Dome_command_moveAz": (False, self.dome_command_move_az),
            "Dome_command_moveEl": (False, self.dome_command_move_el),
            "Dome_command_stopAz": (False, self.dome_command_stop_az),
            "Dome_command_stopEl": (False, self.dome_command_stop_el),
            "quit": (False, self.quit),
        }
        # Name of a command to report as failed once, the next time it is seen,
        # or None if no failures. Used to test CSC handling of failed commands.
        self.fail_command = None

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

    async def cmd_loop(self, reader, writer):
        """Execute commands and output replies."""
        self.log.info("cmd_loop begins")
        writer.write("Enter Command > ".encode())
        await writer.drain()
        while True:
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
            if line:
                try:
                    items = line.split()
                    cmd = items[-1]
                    if cmd not in self.dispatch_dict:
                        raise KeyError(f"Unsupported command {cmd}")
                    if cmd == self.fail_command:
                        self.fail_command = None
                        outputs = [f"Command {cmd} failed by request"]
                    else:
                        has_data, func = self.dispatch_dict[cmd]
                        desired_len = 2 if has_data else 1
                        if len(items) != desired_len:
                            raise RuntimeError(
                                f"{line} split into {len(items)} pieces; expected {desired_len}"
                            )
                        if has_data:
                            outputs = await func(items[0], writer)
                        else:
                            outputs = await func(writer)
                    if outputs:
                        for msg in outputs:
                            writer.write(f"{msg}\n".encode())
                except (KeyError, RuntimeError):
                    self.log.exception(f"command {line} failed")
            writer.write("Enter Command > ".encode())
            await writer.drain()

    async def status(self, writer):
        self.log.info("Received command 'status'")
        writer.write(("AMCS: standby, positionError=0.0, positionActual=0.0, positionCmd=0.0, "
                      + "driveTorqueActual=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueError=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueCmd=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveCurrentActual=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTempActual=[20.0, 20.0, 20.0, 20.0, 20.0], "
                      + "encoderHeadRaw=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "encoderHeadCalibrated=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "resolverRaw=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "resolverCalibrated=[0.0, 0.0, 0.0, 0.0, 0.0]\n")
                     .encode())
        writer.write(("ApSCS: standby, positionError=0.0, positionActual=0.0, positionCmd=0.0, "
                      + "driveTorqueActual=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueError=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueCmd=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveCurrentActual=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTempActual=[20.0, 20.0, 20.0, 20.0, 20.0], "
                      + "resolverRaw=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "resolverCalibrated=[0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "powerAbsortion=0.0\n")
                     .encode())
        writer.write(("LCS: standby, "
                      + "positionError=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "positionActual=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "positionCmd=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueActual=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueError=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTorqueCmd=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveCurrentActual=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "driveTempActual=[20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0], "
                      + "encoderHeadRaw=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "encoderHeadCalibrated=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "
                      + "0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "
                      + "powerAbsortion=0.0\n").encode())
        writer.write(("LWCS: standby, positionError=0.0, positionActual=0.0, positionCmd=0.0, "
                      + "driveTorqueActual=[0.0, 0.0], "
                      + "driveTorqueError=[0.0, 0.0], "
                      + "driveTorqueCmd=[0.0, 0.0], "
                      + "driveCurrentActual=[0.0, 0.0], "
                      + "driveTempActual=[20.0, 20.0], "
                      + "encoderHeadRaw=[0.0, 0.0], "
                      + "encoderHeadCalibrated=[0.0, 0.0], "
                      + "resolverRaw=[0.0, 0.0], "
                      + "resolverCalibrated=[0.0, 0.0], "
                      + "powerAbsortion=0.0\n").encode())
        writer.write(("ThCS: standby, "
                      + "data=[20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0, 20.0, 20.0, 20.0]\n").encode())
        writer.write(("MonCS: standby, "
                      + "data=[20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, "
                      + "20.0, 20.0, 20.0, 20.0]\n").encode())
        await writer.drain()

    async def dome_command_move_az(self, writer):
        self.log.info("Received command 'Dome_command_moveAz'")
        writer.write("Dome_command_moveAz\n".encode())
        await writer.drain()

    async def dome_command_move_el(self, writer):
        self.log.info("Received command 'Dome_command_moveEl'")
        writer.write("Dome_command_moveEl\n".encode())
        await writer.drain()

    async def dome_command_stop_az(self, writer):
        self.log.info("Received command 'Dome_command_stopAz'")
        writer.write("Dome_command_stopAz\n".encode())
        await writer.drain()

    async def dome_command_stop_el(self, writer):
        self.log.info("Received command 'Dome_command_stopEl'")
        writer.write("Dome_command_stopEl\n".encode())
        await writer.drain()

    async def quit(self, writer):
        self.log.info("Received command 'quit'")
        writer.write("quitting now\n".encode())
        await writer.drain()
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

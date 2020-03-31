__all__ = ["DomeCsc"]

import asyncio
import logging
import pathlib
from lsst.ts import salobj
from .mock_controller import MockDomeController

logging.basicConfig(level=logging.INFO)

_LOCAL_HOST = "127.0.0.1"


class DomeCsc(salobj.ConfigurableCsc):
    """
    Upper level Commandable SAL Component to interface with the LSST Dome lower level components.
    """

    def __init__(
        self,
        config_dir=None,
        initial_state=salobj.State.STANDBY,
        simulation_mode=0,
        mock_port=None,
    ):
        schema_path = (
            pathlib.Path(__file__).resolve().parents[4].joinpath("schema", "Dome.yaml")
        )

        self.reader = None
        self.writer = None
        self.config = None

        self.mock_ctrl = None  # mock controller, or None if not constructed
        self.mock_port = mock_port  # mock port, or None if not used
        super().__init__(
            name="Dome",
            index=0,
            schema_path=schema_path,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )
        self.log.info("__init__")

    async def connect(self):
        """Connect to the dome controller's TCP/IP port.

        Start the mock controller, if simulating.
        """
        self.log.info("connect")
        self.log.info(self.config)
        self.log.info(f"self.simulation_mode = {self.simulation_mode}")
        if self.config is None:
            raise RuntimeError("Not yet configured")
        if self.connected:
            raise RuntimeError("Already connected")
        if self.simulation_mode == 1:
            await self.start_mock_ctrl()
            host = _LOCAL_HOST
        else:
            host = self.config.host
        if self.simulation_mode != 0:
            if self.mock_ctrl is None:
                raise RuntimeError("In simulation mode but no mock controller found.")
            port = self.mock_ctrl.port
        else:
            port = self.config.port
        connect_coro = asyncio.open_connection(host=host, port=port)
        self.reader, self.writer = await asyncio.wait_for(
            connect_coro, timeout=self.config.connection_timeout
        )
        self.log.info("connected")

    async def disconnect(self):
        """Disconnect from the TCP/IP controller, if connected, and stop
        the mock controller, if running.
        """
        self.log.debug("disconnect")
        writer = self.writer
        self.reader = None
        self.writer = None
        if writer:
            try:
                writer.write_eof()
                await asyncio.wait_for(writer.drain(), timeout=2)
            finally:
                writer.close()
        await self.stop_mock_ctrl()

    async def start_mock_ctrl(self):
        """Start the mock controller.

        The simulation mode must be 1.
        """
        self.log.info("start_mock_ctrl")
        try:
            assert self.simulation_mode == 1
            if self.mock_port is not None:
                port = self.mock_port
            else:
                port = self.config.port
            self.mock_ctrl = MockDomeController(port)
            await asyncio.wait_for(self.mock_ctrl.start(), timeout=2)
        except Exception as e:
            err_msg = "Could not start mock controller"
            self.log.exception(e)
            self.fault(code=3, report=f"{err_msg}: {e}")
            raise

    async def stop_mock_ctrl(self):
        """Stop the mock controller, if running.
        """
        self.log.info("stop_mock_ctrl")
        mock_ctrl = self.mock_ctrl
        self.mock_ctrl = None
        if mock_ctrl:
            await mock_ctrl.stop()

    async def handle_summary_state(self):
        self.log.info("handle_summary_state")
        if self.disabled_or_enabled:
            if not self.connected:
                await self.connect()
        else:
            await self.disconnect()

    async def do_moveAz(self, data):
        """ Move AZ
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_moveEl(self, data):
        """ Move El
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopAz(self, data):
        """ Stop AZ
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopEl(self, data):
        """ Stop El
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stop(self, data):
        """ Stop
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_crawlAz(self, data):
        """ Crawl AZ
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_crawlEl(self, data):
        """ Crawl El
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_setLouver(self, data):
        """ Set Louver
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_closeLouvers(self, data):
        """ Close Louvers
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopLouvers(self, data):
        """ Stop Louvers
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_openShutter(self, data):
        """ Open Shutter
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_closeShutter(self, data):
        """ Close Shutter
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopShutter(self, data):
        """ Stop Shutter
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_park(self, data):
        """ Park
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_setTemperature(self, data):
        """ Set Temperature
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def config(self, data):
        """ Config command not to be executed by SAL

        This command will be used to send the values of one or more parameters to configure the lower level
        components.
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def fans(self, data):
        """ Fans command not to be executed by SAL

        This command will be used to switch on or off the fans in the dome.
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def inflate(self, data):
        """ Inflate command not to be executed by SAL

        This command will be used to inflate or deflate the inflatable seal.
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def status(self, data):
        """ Status command not to be executed by SAL

        This command will be used to request the full status of all lower level components.
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def close_tasks(self):
        """Disconnect from the TCP/IP controller, if connected, and stop
        the mock controller, if running.
        """
        await super().close_tasks()
        await self.disconnect()

    async def configure(self, config):
        self.config = config

    async def implement_simulation_mode(self, simulation_mode):
        if simulation_mode not in (0, 1):
            raise salobj.ExpectedError(
                f"Simulation_mode={simulation_mode} must be 0 or 1"
            )

    @property
    def connected(self):
        if None in (self.reader, self.writer):
            return False
        return True

    @staticmethod
    def get_config_pkg():
        return "ts_config_mttcs"

    @classmethod
    def add_arguments(cls, parser):
        super(DomeCsc, cls).add_arguments(parser)
        parser.add_argument(
            "-s", "--simulate", action="store_true", help="Run in simuation mode?"
        )

    @classmethod
    def add_kwargs_from_args(cls, args, kwargs):
        super(DomeCsc, cls).add_kwargs_from_args(args, kwargs)
        kwargs["simulation_mode"] = 1 if args.simulate else 0

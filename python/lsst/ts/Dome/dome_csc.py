# import asyncio
import pathlib
from lsst.ts import salobj

__all__ = ["DomeCsc"]


class DomeCsc(salobj.ConfigurableCsc):
    """
    Upper level Commandable SAL Component to interface with the LSST Dome lower level components.
    """

    def __init__(
        self, config_dir=None, initial_state=salobj.State.STANDBY, simulation_mode=0,
    ):
        schema_path = (
            pathlib.Path(__file__).resolve().parents[4].joinpath("schema", "Dome.yaml")
        )

        self.reader = None
        self.writer = None
        self.config = None

        # Tasks that are run to execute specific functionality.
        self.status_task = salobj.make_done_future()
        self.connect_task = salobj.make_done_future()

        self.mock_ctrl = None  # mock controller, or None if not constructed
        super().__init__(
            name="Dome",
            index=0,
            schema_path=schema_path,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

    async def do_moveAz(self, data):
        """
        Move AZ
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_moveEl(self, data):
        """
        Move El
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopAz(self, data):
        """
        Stop AZ
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopEl(self, data):
        """
        Stop El
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stop(self, data):
        """
        Stop
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_crawlAz(self, data):
        """
        Crawl AZ
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_crawlEl(self, data):
        """
        Crawl El
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_setLouver(self, data):
        """
        Set Louver
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_closeLouvers(self, data):
        """
        Close Louvers
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopLouvers(self, data):
        """
        Stop Louvers
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_openShutter(self, data):
        """
        Open Shutter
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_closeShutter(self, data):
        """
        Close Shutter
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_stopShutter(self, data):
        """
        Stop Shutter
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_park(self, data):
        """
        Park
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def do_setTemperature(self, data):
        """
        Set Temperature
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def config(self, data):
        """
        Internal Config command
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def fans(self, data):
        """
        Internal Fans command
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def inflate(self, data):
        """
        Internal Inflate command
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    async def status(self, data):
        """
        Internal Status command
        """
        self.assert_enabled()
        raise salobj.ExpectedError("Not implemented")

    @property
    def connected(self):
        if None in (self.reader, self.writer):
            return False
        return True

    @staticmethod
    def get_config_pkg():
        return "ts_config_mttcs"

    async def configure(self, config):
        self.config = config

    async def implement_simulation_mode(self, simulation_mode):
        if simulation_mode not in (0, 1):
            raise salobj.ExpectedError(
                f"Simulation_mode={simulation_mode} must be 0 or 1"
            )

    @classmethod
    def add_kwargs_from_args(cls, args, kwargs):
        super(DomeCsc, cls).add_kwargs_from_args(args, kwargs)
        kwargs["simulation_mode"] = 1 if args.simulate else 0

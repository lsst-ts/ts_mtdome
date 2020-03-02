# import asyncio
import pathlib
from lsst.ts import salobj

__all__ = ['DomeCsc']


class DomeCsc(salobj.ConfigurableCsc):
    """
    Upper level Commandable SAL Component to interface with the LSST Dome lower level components.
    """

    def __init__(
            self,
            config_dir=None,
            initial_state=salobj.State.STANDBY,
            simulation_mode=0,
    ):
        schema_path = (
            pathlib.Path(__file__)
            .resolve()
            .parents[4]
            .joinpath("schema", "Dome.yaml")
        )

        self.reader = None
        self.writer = None
        self.config = None

        self.mock_ctrl = None  # mock controller, or None if not constructed
        super().__init__(
            name="DCS",
            index=0,
            schema_path=schema_path,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

    async def do_crawlAz(self, data):
        """
        Crawl AZ
        """
        self.assert_enabled("crawlAz")
        pass

    async def do_crawlEl(self, data):
        """
        Crawl El
        """
        self.assert_enabled("crawlEl")
        pass

    async def do_moveAz(self, data):
        """
        Move AZ
        """
        self.assert_enabled("moveAz")
        pass

    async def do_moveEl(self, data):
        """
        Move El
        """
        self.assert_enabled("moveEl")
        pass

    async def do_park(self, data):
        """
        Park
        """
        self.assert_enabled("park")
        pass

    async def do_setLouver(self, data):
        """
        Set Louver
        """
        self.assert_enabled("setLouver")
        pass

    async def do_closeLouvers(self, data):
        """
        Close Louvers
        """
        self.assert_enabled("closeLouvers")
        pass

    async def do_stopLouvers(self, data):
        """
        Stop Louvers
        """
        self.assert_enabled("stopLouvers")
        pass

    async def do_closeShutter(self, data):
        """
        Close Shutter
        """
        self.assert_enabled("closeShutter")
        pass

    async def do_openShutter(self, data):
        """
        Open Shutter
        """
        self.assert_enabled("openShutter")
        pass

    async def do_stopShutter(self, data):
        """
        Stop Shutter
        """
        self.assert_enabled("stopShutter")
        pass

    async def do_stopAz(self, data):
        """
        Stop AZ
        """
        self.assert_enabled("stopAz")
        pass

    async def do_stopEl(self, data):
        """
        Stop El
        """
        self.assert_enabled("stopEl")
        pass

    async def do_stop(self, data):
        """
        Stop
        """
        self.assert_enabled("stop")
        pass

    async def do_setTemperature(self, data):
        """
        Set Temperature
        """
        self.assert_enabled("setTemperature")
        pass

    @staticmethod
    def get_config_pkg():
        return "ts_config_mttcs"

    async def configure(self, config):
        self.config = config
        # self.evt_settingsAppliedDomeTcp.set_put(
        #     host=self.config.host,
        #     port=self.config.port,
        #     connectionTimeout=self.config.connection_timeout,
        #     readTimeout=self.config.read_timeout,
        #     force_output=True,
        # )

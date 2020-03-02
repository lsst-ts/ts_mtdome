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

    async def do_Dome_command_crawlAz(self, id_data):
        """
        Crawl AZ
        """
        pass

    async def do_Dome_command_crawlEl(self, id_data):
        """
        Crawl El
        """
        pass

    async def do_Dome_command_moveAz(self, id_data):
        """
        Move AZ
        """
        pass

    async def do_Dome_command_moveEl(self, id_data):
        """
        Move El
        """
        pass

    async def do_Dome_command_park(self, id_data):
        """
        Park
        """
        pass

    async def do_Dome_command_setLouver(self, id_data):
        """
        Set Louver
        """
        pass

    async def do_Dome_command_closeLouvers(self, id_data):
        """
        Close Louvers
        """
        pass

    async def do_Dome_command_stopLouvers(self, id_data):
        """
        Stop Louvers
        """
        pass

    async def do_Dome_command_closeShutter(self, id_data):
        """
        Close Shutter
        """
        pass

    async def do_Dome_command_openShutter(self, id_data):
        """
        Open Shutter
        """
        pass

    async def do_Dome_command_stopShutter(self, id_data):
        """
        Stop Shutter
        """
        pass

    async def do_Dome_command_stopAz(self, id_data):
        """
        Stop AZ
        """
        pass

    async def do_Dome_command_stopEl(self, id_data):
        """
        Stop El
        """
        pass

    async def do_Dome_command_stop(self, id_data):
        """
        Stop
        """
        pass

    async def do_Dome_command_setTemperature(self, id_data):
        """
        Set Temperature
        """
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

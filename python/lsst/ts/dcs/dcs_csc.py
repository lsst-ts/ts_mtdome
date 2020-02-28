# import asyncio
import pathlib
from lsst.ts import salobj

__all__ = ['DCSCSC']


class DCSCSC(salobj.ConfigurableCsc):
    """
    Upper level Commandable SAL Component to interface with the LSST Dome lower level components.
    """

    def __init__(
            self,
            config_dir=None,
            initial_state=salobj.State.STANDBY,
            simulation_mode=0,
    ):
        """
        Initialize DIMM CSC.
        """
        schema_path = (
            pathlib.Path(__file__)
            .resolve()
            .parents[4]
            .joinpath("schema", "dcs.yaml")
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

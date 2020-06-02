__all__ = ["DomeCsc"]

import asyncio
import logging
import math
import pathlib

import numpy as np

from .error_code import ErrorCode
from .llc_configuration_limits import AmcsLimits, LwscsLimits
from .llc_name import LlcName
from lsst.ts import salobj
from lsst.ts.Dome import encoding_tools
from .mock_controller import MockDomeController

_LOCAL_HOST = "127.0.0.1"
_TIMEOUT = 20  # timeout in s to be used by this module
_KEYS_TO_REMOVE = {"status"}
_KEYS_IN_RADIANS = {"positionError", "positionActual", "positionCmd"}


class DomeCsc(salobj.ConfigurableCsc):
    """Upper level Commandable SAL Component to interface with the LSST Dome lower level components.

    Parameters
    ----------
    config_dir : `string`
        The configuration directory
    initial_state : `salobj.State`
        The initial state of the CSC
    simulation_mode : `int`
        Simulation mode (1) or not (0)
    mock_port : `int`
        The port that the mock controller will listen on
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

        self.log = logging.getLogger("DomeCsc")

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

        self.lower_level_status = None
        self.status_task = None

        self.amcs_limits = AmcsLimits()
        self.lwscs_limits = LwscsLimits()

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
            port = self.mock_ctrl.port
        else:
            host = self.config.host
            port = self.config.port
        connect_coro = asyncio.open_connection(host=host, port=port)
        self.reader, self.writer = await asyncio.wait_for(
            connect_coro, timeout=self.config.connection_timeout
        )

        # Start polling for the status of the lower level components periodically.
        self.status_task = asyncio.create_task(
            self.schedule_task_periodically(1, self.status)
        )

        self.log.info("connected")

    async def disconnect(self):
        """Disconnect from the TCP/IP controller, if connected, and stop the mock controller, if running.
        """
        self.log.info("disconnect")

        # Stop polling for the status of the lower level components periodically.
        if self.status_task:
            self.status_task.cancel()

        writer = self.writer
        self.reader = None
        self.writer = None
        await self.stop_mock_ctrl()
        if writer:
            try:
                writer.write_eof()
                await asyncio.wait_for(writer.drain(), timeout=2)
            finally:
                writer.close()

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
            await asyncio.wait_for(self.mock_ctrl.start(), timeout=_TIMEOUT)

        except Exception as e:
            err_msg = "Could not start mock controller"
            self.log.error(e)
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
        """Override of the handle_summary_state function to connect or disconnect to the lower level
        components (or the mock_controller) when needed.
        """
        self.log.info(f"handle_summary_state {salobj.State(self.summary_state).name}")
        if self.disabled_or_enabled:
            if not self.connected:
                await self.connect()
        else:
            await self.disconnect()

    async def write_then_read_reply(self, cmd, **params):
        """Write the cmd string and then read the reply to the command.

        Parameters
        ----------
        cmd: `str`
            The command to write.
        **params:
            The parameters for the command cmd. This may be empty.

        Returns
        -------
        configuration_parameters : `dict`
            A dict of the form {"reply": {"param1": value1, "param2": value2}} where "reply" can for
            instance be "OK" or "ERROR".
         """
        st = encoding_tools.encode(cmd, **params)
        self.log.info(f"Sending command {st}")
        self.writer.write(st.encode() + b"\r\n")
        await self.writer.drain()
        read_bytes = await asyncio.wait_for(self.reader.readuntil(b"\r\n"), timeout=1)
        data = encoding_tools.decode(read_bytes.decode())

        if "ERROR" in data.keys():
            self.log.error(f"Received ERROR {data}.")
            if ErrorCode(data["ERROR"]["CODE"]) == ErrorCode.INCORRECT_PARAMETER:
                raise ValueError(f"The command {cmd} contains an incorrect parameter.")
            elif ErrorCode(data["ERROR"]["CODE"]) == ErrorCode.UNSUPPORTED_COMMAND:
                raise KeyError(f"The command {cmd} is unsupported.")

        return data

    async def do_moveAz(self, data):
        """Move AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.info(
            f"Moving Dome to azimuth {data.azimuth} and gthen start crawling at azRate {data.azRate}"
        )
        await self.write_then_read_reply(
            "moveAz",
            azimuth=math.radians(data.azimuth),
            azRate=math.radians(data.azRate),
        )

    async def do_moveEl(self, data):
        """Move El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.info(f"Moving LWS to elevation {data.elevation}")
        await self.write_then_read_reply(
            "moveEl", elevation=math.radians(data.elevation)
        )

    async def do_stopAz(self, data):
        """Stop AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("stopAz")

    async def do_stopEl(self, data):
        """Stop El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("stopEl")

    async def do_stop(self, data):
        """Stop.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("stop")

    async def do_crawlAz(self, data):
        """Crawl AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("crawlAz", azRate=math.radians(data.azRate))

    async def do_crawlEl(self, data):
        """Crawl El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("crawlEl", elRate=math.radians(data.elRate))

    async def do_setLouver(self, data):
        """Set Louver.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            "setLouver", id=data.id, position=math.radians(data.position)
        )

    async def do_closeLouvers(self, data):
        """Close Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("closeLouvers")

    async def do_stopLouvers(self, data):
        """Stop Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("stopLouvers")

    async def do_openShutter(self, data):
        """Open Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("openShutter")

    async def do_closeShutter(self, data):
        """Close Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("closeShutter")

    async def do_stopShutter(self, data):
        """Stop Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("stopShutter")

    async def do_park(self, data):
        """Park.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("park")

    async def do_setTemperature(self, data):
        """Set Temperature.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply("setTemperature", temperature=data.temperature)

    async def config_llcs(self, data):
        """Config command not to be executed by SAL.

        This command will be used to send the values of one or more parameters to configure the lower level
        components.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain keys for all lower level
            components to be configured with values that are dicts with keys for all the parameters that
            need to be configured. The structure is::

                "AMCS":
                    "jmax"
                    "amax"
                    "vmax"
                "LWSCS":
                    "jmax"
                    "amax"
                    "vmax"

        It is assumed that configuration_parameters is presented as a dictionary of dictionaries with one
        dictionary per lower level component. This means that we only need to check for unknown and too
        large parameters and then send all to the lower level components. An example would be::

            {"AMCS": {"amax": 5, "jmax": 4}, "LWSCS": {"vmax": 5, "jmax": 4}}

        """
        amcs_configuration_parameters = data[LlcName.AMCS.value]
        amcs_config_params = self.amcs_limits.validate(amcs_configuration_parameters)

        lwscs_configuration_parameters = data[LlcName.LWSCS.value]
        lwscs_config_params = self.lwscs_limits.validate(lwscs_configuration_parameters)

        await self.write_then_read_reply(
            "config", AMCS=amcs_config_params, LWCS=lwscs_config_params
        )

    async def fans(self, data):
        """Fans command not to be executed by SAL.

        This command will be used to switch on or off the fans in the dome.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply("fans", action=data["action"])

    async def inflate(self, data):
        """Inflate command not to be executed by SAL.

        This command will be used to inflate or deflate the inflatable seal.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply("inflate", action=data["action"])

    async def status(self):
        """Status command not to be executed by SAL.

        This command will be used to request the full status of all lower level components.
        """
        self.lower_level_status = await self.write_then_read_reply("status")
        self.log.info(self.lower_level_status)

        self.convert_telemetry_radians_to_degrees_and_send(
            self.lower_level_status[LlcName.AMCS.value], self.tel_domeADB_status
        )
        self.convert_telemetry_radians_to_degrees_and_send(
            self.lower_level_status[LlcName.APSCS.value], self.tel_domeAPS_status
        )
        self.convert_telemetry_list_radians_to_degrees_and_send(
            self.lower_level_status[LlcName.LCS.value], self.tel_domeLouvers_status
        )
        self.convert_telemetry_radians_to_degrees_and_send(
            self.lower_level_status[LlcName.LWSCS.value], self.tel_domeLWS_status
        )
        self.convert_telemetry_radians_to_degrees_and_send(
            self.lower_level_status[LlcName.MONCS.value], self.tel_domeMONCS_status
        )
        self.convert_telemetry_radians_to_degrees_and_send(
            self.lower_level_status[LlcName.THCS.value], self.tel_domeTHCS_status
        )

    # noinspection PyMethodMayBeStatic
    def convert_telemetry_radians_to_degrees_and_send(
        self, telemetry_in_radians, telemetry_function
    ):
        telemetry_in_degrees = {}
        for key in telemetry_in_radians.keys():
            if key in _KEYS_IN_RADIANS:
                telemetry_in_degrees[key] = math.degrees(telemetry_in_radians[key])
            else:
                # No conversion needed since the value does not express an angle
                telemetry_in_degrees[key] = telemetry_in_radians[key]
        # Remove some keys because they are not reported in the telemetry.
        telemetry = self.remove_keys_from_dict(telemetry_in_degrees)
        # Send the telemetry.
        self.send_telemetry(telemetry, telemetry_function)

    # noinspection PyMethodMayBeStatic
    def convert_telemetry_list_radians_to_degrees_and_send(
        self, telemetry_in_radians, telemetry_function
    ):
        telemetry_in_degrees = {}
        for key in telemetry_in_radians.keys():
            if key in _KEYS_IN_RADIANS:
                telemetry_in_degrees[key] = np.degrees(
                    np.array(telemetry_in_radians[key])
                )
            else:
                # No conversion needed since the value does not express an angle
                telemetry_in_degrees[key] = telemetry_in_radians[key]
        # Remove some keys because they are not reported in the telemetry.
        telemetry = self.remove_keys_from_dict(telemetry_in_degrees)
        # Send the telemetry.
        self.send_telemetry(telemetry, telemetry_function)

    # noinspection PyMethodMayBeStatic
    def remove_keys_from_dict(self, dict_with_too_many_keys):
        """
        Return a copy of a dict with specified items removed.

        Parameters
        ----------
        dict_with_too_many_keys : `dict`
            The dict where to remove the keys from.

        Returns
        -------
        dict_with_keys_removed : `dict`
            A dict with the same keys as the given dict but with the given keys removed.
        """
        dict_with_keys_removed = {
            x: dict_with_too_many_keys[x]
            for x in dict_with_too_many_keys
            if x not in _KEYS_TO_REMOVE
        }
        return dict_with_keys_removed

    # noinspection PyMethodMayBeStatic
    def send_telemetry(self, telemetry, telemetry_function):
        """Prepares the telemetry for sending using the provided status and sends it.

        Parameters
        ----------
        telemetry: `dict`
            The lower level telemetry to extract the telemetry from.
        telemetry_function: func
            The SAL function that send the specific telemetry.
        """
        # Remove some keys because they are not reported in the telemetry.
        telemetry_function.set_put(**telemetry)

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

    # noinspection PyMethodMayBeStatic
    async def schedule_task_periodically(self, period, task):
        """Schedules a task periodically.

        Parameters
        ----------
        period : int
            The period in (decimal) seconds at which to schedule the function.
        task : coroutine
            The function to be scheduled periodically.
        """
        while True:
            await task()
            await asyncio.sleep(period)

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

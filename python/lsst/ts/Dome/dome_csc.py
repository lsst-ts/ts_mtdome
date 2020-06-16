__all__ = ["DomeCsc"]

import asyncio
import logging
import math
import pathlib

import numpy as np

from .llc_configuration_limits import AmcsLimits, LwscsLimits
from .llc_name import LlcName
from lsst.ts import salobj
from lsst.ts.Dome import encoding_tools
from .mock_controller import MockDomeController
from .response_code import ResponseCode

_LOCAL_HOST = "127.0.0.1"
_TIMEOUT = 20  # timeout in s to be used by this module
_KEYS_TO_REMOVE = {"status"}
_KEYS_IN_RADIANS = {"positionError", "positionActual", "positionCommanded"}

_STATUS_TASK_PERIOD = 0.2
_AMCS_PERIOD = 2.0
_APsCS_PERIOD = 2.0
_LCS_PERIOD = 2.0
_LWSCS_PERIOD = 2.0
_MonCS_PERIOD = 2.0
_ThCS_PERIOD = 2.0


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

        # Keep the lower level statuses in memory for unit tests.
        self.lower_level_status = {}
        self.llc_status_task = None

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

        # Start polling for the status of the AMCS component periodically at a frequency of 5 Hz.
        self.llc_status_task = asyncio.create_task(
            self.schedule_llc_tasks_periodically()
        )

        self.log.info("connected")

    async def disconnect(self):
        """Disconnect from the TCP/IP controller, if connected, and stop the mock controller, if running.
        """
        self.log.info("disconnect")

        # Stop polling for the status of the lower level components periodically.
        if self.llc_status_task:
            self.llc_status_task.cancel()

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

    async def write_then_read_reply(self, **params):
        """Write the cmd string and then read the reply to the command.

        Parameters
        ----------
        **params:
            The parameters for the command cmd. This may be empty.

        Returns
        -------
        configuration_parameters : `dict`
            A dict of the form {"reply": {"param1": value1, "param2": value2}} where "reply" can for
            instance be "OK" or "ERROR".
         """
        cmd = params["command"]
        st = encoding_tools.encode(**params)
        self.log.debug(f"Sending command {st}")
        self.writer.write(st.encode() + b"\r\n")
        await self.writer.drain()
        read_bytes = await asyncio.wait_for(self.reader.readuntil(b"\r\n"), timeout=1)
        data = encoding_tools.decode(read_bytes.decode())

        response = data["response"]
        if response > ResponseCode.OK:
            self.log.error(f"Received ERROR {data}.")
            if response == ResponseCode.INCORRECT_PARAMETER:
                raise ValueError(f"The command {cmd} contains an incorrect parameter.")
            elif response == ResponseCode.UNSUPPORTED_COMMAND:
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
        self.log.debug(
            f"Moving Dome to azimuth {data.position} and gthen start crawling at azRate {data.velocity}"
        )
        await self.write_then_read_reply(
            command="moveAz",
            parameters={
                "position": math.radians(data.position),
                "velocity": math.radians(data.velocity),
            },
        )

    async def do_moveEl(self, data):
        """Move El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        self.log.debug(f"Moving LWS to elevation {data.position}")
        await self.write_then_read_reply(
            command="moveEl", parameters={"position": math.radians(data.position)}
        )

    async def do_stopAz(self, data):
        """Stop AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopAz", parameters={})

    async def do_stopEl(self, data):
        """Stop El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopEl", parameters={})

    async def do_stop(self, data):
        """Stop.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stop", parameters={})

    async def do_crawlAz(self, data):
        """Crawl AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="crawlAz", parameters={"velocity": math.radians(data.velocity)}
        )

    async def do_crawlEl(self, data):
        """Crawl El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="crawlEl", parameters={"velocity": math.radians(data.velocity)}
        )

    async def do_setLouvers(self, data):
        """Set Louver.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="setLouvers", parameters={"position": data.position},
        )

    async def do_closeLouvers(self, data):
        """Close Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="closeLouvers", parameters={})

    async def do_stopLouvers(self, data):
        """Stop Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopLouvers", parameters={})

    async def do_openShutter(self, data):
        """Open Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="openShutter", parameters={})

    async def do_closeShutter(self, data):
        """Close Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="closeShutter", parameters={})

    async def do_stopShutter(self, data):
        """Stop Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopShutter", parameters={})

    async def do_park(self, data):
        """Park.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="park", parameters={})

    async def do_setTemperature(self, data):
        """Set Temperature.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="setTemperature", parameters={"temperature": data.temperature}
        )

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
            command="config",
            parameters={"AMCS": amcs_config_params, "LWCS": lwscs_config_params},
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
        await self.write_then_read_reply(
            command="fans", parameters={"action": data["action"]}
        )

    async def inflate(self, data):
        """Inflate command not to be executed by SAL.

        This command will be used to inflate or deflate the inflatable seal.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply(
            command="inflate", parameters={"action": data["action"]}
        )

    async def statusAMCS(self):
        """AMCS status command not to be executed by SAL.

        This command will be used to request the full status of the AMCS lower level component.
        """
        await self.request_and_send_llc_status(LlcName.AMCS, self.tel_azimuth)

    async def statusApSCS(self):
        """ApSCS status command not to be executed by SAL.

        This command will be used to request the full status of the ApSCS lower level component.
        """
        await self.request_and_send_llc_status(LlcName.APSCS, self.tel_apertureShutter)

    async def statusLCS(self):
        """LCS status command not to be executed by SAL.

        This command will be used to request the full status of the LCS lower level component.
        """
        await self.request_and_send_llc_status(LlcName.LCS, self.tel_louvers)

    async def statusLWSCS(self):
        """LWSCS status command not to be executed by SAL.

        This command will be used to request the full status of the LWSCS lower level component.
        """
        await self.request_and_send_llc_status(LlcName.LWSCS, self.tel_lightWindScreen)

    async def statusMonCS(self):
        """MonCS status command not to be executed by SAL.

        This command will be used to request the full status of the MonCS lower level component.
        """
        await self.request_and_send_llc_status(LlcName.MONCS, self.tel_interlocks)

    async def statusThCS(self):
        """ThCS status command not to be executed by SAL.

        This command will be used to request the full status of the ThCS lower level component.
        """
        await self.request_and_send_llc_status(LlcName.THCS, self.tel_thermal)

    async def request_and_send_llc_status(self, llc_name, telemetry_function):
        command = f"status{llc_name.value}"
        status = await self.write_then_read_reply(command=command, parameters={})
        # Store the status for unit tests.
        self.lower_level_status[llc_name.value] = status[llc_name.value][0]
        if llc_name == LlcName.LWSCS:
            self.convert_telemetry_list_radians_to_degrees_and_send(
                status[llc_name.value][0], telemetry_function
            )
        else:
            self.convert_telemetry_radians_to_degrees_and_send(
                status[llc_name.value][0], telemetry_function, llc_name
            )

    def convert_telemetry_radians_to_degrees_and_send(
        self, telemetry_in_radians, telemetry_function, llc_name
    ):
        telemetry_in_degrees = {}
        for key in telemetry_in_radians.keys():
            # LWSCS is handled by convert_telemetry_list_radians_to_degrees_and_send
            if key in _KEYS_IN_RADIANS and llc_name == LlcName.AMCS:
                telemetry_in_degrees[key] = math.degrees(telemetry_in_radians[key])
            else:
                # No conversion needed since the value does not express an angle
                telemetry_in_degrees[key] = telemetry_in_radians[key]
        # Remove some keys because they are not reported in the telemetry.
        telemetry = self.remove_keys_from_dict(telemetry_in_degrees)
        # Send the telemetry.
        self.send_telemetry(telemetry, telemetry_function)

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
        self.log.info(f"telemetry before = {telemetry}")
        telemetry_function.set_put(**telemetry)
        self.log.info(f"telemetry after = {telemetry}")

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

    async def schedule_llc_tasks_periodically(self):
        """Schedules the LLC status tasks periodically.
        """
        start_tai = salobj.current_tai()
        try:
            while True:
                current_tai = salobj.current_tai()
                reset_start_tai = False
                if (current_tai - start_tai) > _AMCS_PERIOD:
                    await self.statusAMCS()
                    reset_start_tai = True
                if (current_tai - start_tai) > _APsCS_PERIOD:
                    await self.statusApSCS()
                    reset_start_tai = True
                if (current_tai - start_tai) > _LCS_PERIOD:
                    await self.statusLCS()
                    reset_start_tai = True
                if (current_tai - start_tai) > _LWSCS_PERIOD:
                    await self.statusLWSCS()
                    reset_start_tai = True
                if (current_tai - start_tai) > _MonCS_PERIOD:
                    await self.statusMonCS()
                    reset_start_tai = True
                if (current_tai - start_tai) > _ThCS_PERIOD:
                    await self.statusThCS()
                    reset_start_tai = True

                if reset_start_tai:
                    start_tai = current_tai

                await asyncio.sleep(_STATUS_TASK_PERIOD)
        except Exception as e:
            self.log.error(e)

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

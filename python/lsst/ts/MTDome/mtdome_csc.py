# This file is part of ts_MTDome.
#
# Developed for the LSST Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = ["MTDomeCsc"]

import asyncio
import math
import pathlib

from .llc_configuration_limits import AmcsLimits, LwscsLimits
from .llc_name import LlcName
from lsst.ts import salobj
from lsst.ts.MTDome import encoding_tools
from .mock_controller import MockMTDomeController
from .response_code import ResponseCode
from lsst.ts.idl.enums.MTDome import EnabledState, MotionState

_LOCAL_HOST = "127.0.0.1"
_TIMEOUT = 20  # timeout in s to be used by this module
# DM-26653: Added "positionError" since this key is still under discussion.
_KEYS_TO_REMOVE = {"status", "positionError"}
_KEYS_IN_RADIANS = {"positionError", "positionActual", "positionCommanded"}

_AMCS_STATUS_PERIOD = 0.2
_APsCS_STATUS_PERIOD = 2.0
_LCS_STATUS_PERIOD = 2.0
_LWSCS_STATUS_PERIOD = 2.0
_MONCS_STATUS_PERIOD = 2.0
_THCS_STATUS_PERIOD = 2.0


class MTDomeCsc(salobj.ConfigurableCsc):
    """Upper level Commandable SAL Component to interface with the Simonyi
    Survey Telescope Dome lower level components.

    Parameters
    ----------
    config_dir : `string`
        The configuration directory
    initial_state : `salobj.State`
        The initial state of the CSC
    simulation_mode : `int`
        Simulation mode. Allowed values:

        * 0: regular operation.
        * 1: simulation: use a mock low level HVAC controller.
    mock_port : `int`
        The port that the mock controller will listen on

    Notes
    -----
    **Simulation Modes**

    Supported simulation modes:

    * 0: regular operation
    * 1: simulation mode: start a mock TCP/IP Dome controller and talk to it
    """

    valid_simulation_modes = (0, 1)

    def __init__(
        self,
        config_dir=None,
        initial_state=salobj.State.STANDBY,
        simulation_mode=0,
        mock_port=None,
    ):
        schema_path = (
            pathlib.Path(__file__)
            .resolve()
            .parents[4]
            .joinpath("schema", "MTDome.yaml")
        )

        self.reader = None
        self.writer = None
        self.config = None

        self.mock_ctrl = None  # mock controller, or None if not constructed
        self.mock_port = mock_port  # mock port, or None if not used

        super().__init__(
            name="MTDome",
            index=0,
            schema_path=schema_path,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        # Keep the lower level statuses in memory for unit tests.
        self.lower_level_status = {}
        self.status_tasks = []

        # Keep a lock so only one remote command can be executed at a time.
        self.communication_lock = asyncio.Lock()

        self.amcs_limits = AmcsLimits()
        self.lwscs_limits = LwscsLimits()
        self.log.info("DomeCsc constructed")

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

        # DM-26374: Send enabled events for az and el since they are always
        # enabled.
        self.evt_azEnabled.set_put(state=EnabledState.ENABLED)
        self.evt_elEnabled.set_put(state=EnabledState.ENABLED)

        # DM-26374: Send events for the brakes, interlocks and locking pins
        # with a default value of 0 (meaning nothing engaged) until the
        # corresponding enums have been defined. This will be done in DM-26863.
        self.evt_brakesEngaged.set_put(brakes=0)
        self.evt_interlocks.set_put(interlocks=0)
        self.evt_lockingPinsEngaged.set_put(engaged=0)

        # Start polling for the status of the lower level components
        # periodically.
        await self.start_status_tasks()

        self.log.info("connected")

    async def cancel_status_tasks(self):
        """Cancel all status tasks."""
        while self.status_tasks:
            self.status_tasks.pop().cancel()

    async def start_status_tasks(self):
        """Start all status tasks."""
        await self.cancel_status_tasks()
        for method, interval in (
            (self.statusAMCS, _AMCS_STATUS_PERIOD),
            (self.statusApSCS, _APsCS_STATUS_PERIOD),
            (self.statusLCS, _LCS_STATUS_PERIOD),
            (self.statusLWSCS, _LWSCS_STATUS_PERIOD),
            (self.statusMonCS, _MONCS_STATUS_PERIOD),
            (self.statusThCS, _THCS_STATUS_PERIOD),
        ):
            self.status_tasks.append(
                asyncio.create_task(self.one_status_loop(method, interval))
            )

    async def disconnect(self):
        """Disconnect from the TCP/IP controller, if connected, and stop the
        mock controller, if running.
        """
        self.log.info("disconnect")

        # Stop polling for the status of the lower level components
        # periodically.
        await self.cancel_status_tasks()

        writer = self.writer
        self.reader = None
        self.writer = None
        await self.stop_mock_ctrl()
        if writer:
            try:
                writer.write_eof()
                await asyncio.wait_for(writer.drain(), timeout=_TIMEOUT)
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
            self.mock_ctrl = MockMTDomeController(port)
            await asyncio.wait_for(self.mock_ctrl.start(), timeout=_TIMEOUT)

        except Exception as e:
            err_msg = "Could not start mock controller"
            self.log.error(e)
            self.fault(code=3, report=f"{err_msg}: {e}")
            raise

    async def stop_mock_ctrl(self):
        """Stop the mock controller, if running."""
        self.log.info("stop_mock_ctrl")
        mock_ctrl = self.mock_ctrl
        self.mock_ctrl = None
        if mock_ctrl:
            await mock_ctrl.stop()

    async def handle_summary_state(self):
        """Override of the handle_summary_state function to connect or
        disconnect to the lower level components (or the mock_controller) when
        needed.
        """
        self.log.info(f"handle_summary_state {self.summary_state}")
        if self.disabled_or_enabled:
            if not self.connected:
                await self.connect()
        else:
            await self.disconnect()

    async def write_then_read_reply(self, command, **params):
        """Write the cmd string and then read the reply to the command.

        Parameters
        ----------
        command: `str`
            The command to write.
        **params:
            The parameters for the command. This may be empty.

        Returns
        -------
        data : `dict`
            A dict of the form {"response": ResponseCode, "timeout":
            TimeoutValue} where "response" can be zero for "OK" or non-zero
            for "ERROR".
        """
        command_dict = dict(command=command, parameters=params)
        st = encoding_tools.encode(**command_dict)
        async with self.communication_lock:
            self.log.debug(f"Sending command {st}")
            self.writer.write(st.encode() + b"\r\n")
            await self.writer.drain()
            read_bytes = await asyncio.wait_for(
                self.reader.readuntil(b"\r\n"), timeout=_TIMEOUT
            )
            data = encoding_tools.decode(read_bytes.decode())
            self.log.debug(f"Received reply {data}")

            response = data["response"]
            if response > ResponseCode.OK:
                self.log.error(f"Received ERROR {data}.")
                if response == ResponseCode.INCORRECT_PARAMETER:
                    raise ValueError(
                        f"The command {command} contains an incorrect parameter."
                    )
                elif response == ResponseCode.UNSUPPORTED_COMMAND:
                    raise KeyError(f"The command {command} is unsupported.")

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
            f"Moving Dome to azimuth {data.position} and then start crawling at azRate {data.velocity}"
        )
        await self.write_then_read_reply(
            command="moveAz",
            position=math.radians(data.position),
            velocity=math.radians(data.velocity),
        )
        self.evt_azTarget.set_put(position=data.position, velocity=data.velocity)

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
            command="moveEl", position=math.radians(data.position)
        )
        self.evt_elTarget.set_put(position=data.position, velocity=0)

    async def do_stopAz(self, data):
        """Stop AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopAz")

    async def do_stopEl(self, data):
        """Stop El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopEl")

    async def do_stop(self, data):
        """Stop.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stop")

    async def do_crawlAz(self, data):
        """Crawl AZ.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="crawlAz", velocity=math.radians(data.velocity)
        )
        self.evt_azTarget.set_put(position=float("nan"), velocity=data.velocity)

    async def do_crawlEl(self, data):
        """Crawl El.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="crawlEl", velocity=math.radians(data.velocity)
        )
        self.evt_elTarget.set_put(position=float("nan"), velocity=data.velocity)

    async def do_setLouvers(self, data):
        """Set Louver.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="setLouvers", position=data.position)

    async def do_closeLouvers(self, data):
        """Close Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="closeLouvers")

    async def do_stopLouvers(self, data):
        """Stop Louvers.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopLouvers")

    async def do_openShutter(self, data):
        """Open Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="openShutter")

    async def do_closeShutter(self, data):
        """Close Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="closeShutter")

    async def do_stopShutter(self, data):
        """Stop Shutter.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="stopShutter")

    async def do_park(self, data):
        """Park.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(command="park")
        self.evt_azTarget.set_put(position=0, velocity=0)

    async def do_setTemperature(self, data):
        """Set Temperature.

        Parameters
        ----------
        data : A SALOBJ data object
            Contains the data as defined in the SAL XML file.
        """
        self.assert_enabled()
        await self.write_then_read_reply(
            command="setTemperature", temperature=data.temperature
        )

    async def config_llcs(self, system, settings):
        """Config command not to be executed by SAL.

        This command will be used to send the values of one or more parameters
        to configure the lower level components.

        Parameters
        ----------
        system: `str`
            The name of the lower level component to configure.
        settings : `dict`
            A dict containing key,value for all the parameters that need to be
            configured. The structure is::

                "jmax"
                "amax"
                "vmax"

        """
        self.log.info(f"Settings before validation {settings}")
        if system == LlcName.AMCS.value:
            self.amcs_limits.validate(settings)
        elif system == LlcName.LWSCS.value:
            self.lwscs_limits.validate(settings)
        self.log.info(f"Settings after validation {settings}")

        await self.write_then_read_reply(
            command="config", system=system, settings=settings
        )

    async def fans(self, data):
        """Fans command not to be executed by SAL.

        This command will be used to switch on or off the fans in the dome.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain
            the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply(command="fans", action=data["action"])

    async def inflate(self, data):
        """Inflate command not to be executed by SAL.

        This command will be used to inflate or deflate the inflatable seal.

        Parameters
        ----------
        data : `dict`
            A dictionary with arguments to the function call. It should contain
            the key "action" with a
            string value (ON or OFF).
        """
        await self.write_then_read_reply(command="inflate", action=data["action"])

    async def statusAMCS(self):
        """AMCS status command not to be executed by SAL.

        This command will be used to request the full status of the AMCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.AMCS, self.tel_azimuth)

    async def statusApSCS(self):
        """ApSCS status command not to be executed by SAL.

        This command will be used to request the full status of the ApSCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.APSCS, self.tel_apertureShutter)

    async def statusLCS(self):
        """LCS status command not to be executed by SAL.

        This command will be used to request the full status of the LCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.LCS, self.tel_louvers)

    async def statusLWSCS(self):
        """LWSCS status command not to be executed by SAL.

        This command will be used to request the full status of the LWSCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.LWSCS, self.tel_lightWindScreen)

    async def statusMonCS(self):
        """MonCS status command not to be executed by SAL.

        This command will be used to request the full status of the MonCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.MONCS, self.tel_interlocks)

    async def statusThCS(self):
        """ThCS status command not to be executed by SAL.

        This command will be used to request the full status of the ThCS lower
        level component.
        """
        await self.request_and_send_llc_status(LlcName.THCS, self.tel_thermal)

    async def request_and_send_llc_status(self, llc_name, topic):
        """Generic method for retrieving the status of a lower level component
        and publish that on the corresponding telemetry topic.

        Parameters
        ----------
        llc_name: `LlcName`
            The name of the lower level component.
        topic: SAL topic
            The SAL topic to publish the telemetry to.

        """
        command = f"status{llc_name.value}"
        status = await self.write_then_read_reply(command=command)
        # Store the status for unit tests.
        self.lower_level_status[llc_name.value] = status[llc_name.value]

        telemetry_in_degrees = {}
        telemetry_in_radians = status[llc_name.value]
        for key in telemetry_in_radians.keys():
            if key in _KEYS_IN_RADIANS and llc_name in [LlcName.AMCS, LlcName.LWSCS]:
                telemetry_in_degrees[key] = math.degrees(telemetry_in_radians[key])
            elif key == "timestampUTC":
                # DM-26653: The name of this parameter is still under
                # discussion.
                telemetry_in_degrees["timestamp"] = telemetry_in_radians["timestampUTC"]
            else:
                # No conversion needed since the value does not express an
                # angle
                telemetry_in_degrees[key] = telemetry_in_radians[key]
        # Remove some keys because they are not reported in the telemetry.
        telemetry = self.remove_keys_from_dict(telemetry_in_degrees)
        # Send the telemetry.
        self.send_telemetry(telemetry, topic)

        # DM-26374: Check for errors and send the events.
        if llc_name == LlcName.AMCS:
            status = status[llc_name.value]["status"]
            # The error codes will be specified in a future Dome Software
            # meeting.
            if status["error"] != ["No Error"]:
                fault_code = ", ".join(status["error"])
                self.evt_azEnabled.set_put(
                    state=EnabledState.FAULT, faultCode=fault_code
                )
            else:
                motion_state = MotionState[status["status"]]
                in_position = False
                if motion_state in [
                    MotionState.STOPPED,
                    MotionState.CRAWLING,
                    MotionState.PARKED,
                ]:
                    in_position = True
                self.evt_azMotion.set_put(state=motion_state, inPosition=in_position)
        elif llc_name == LlcName.LWSCS:
            status = status[llc_name.value]["status"]
            motion_state = MotionState[status]
            in_position = False
            if motion_state in [
                MotionState.STOPPED,
                MotionState.CRAWLING,
            ]:
                in_position = True
            self.evt_elMotion.set_put(state=motion_state, inPosition=in_position)

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
            A dict with the same keys as the given dict but with the given keys
            removed.
        """
        dict_with_keys_removed = {
            x: dict_with_too_many_keys[x]
            for x in dict_with_too_many_keys
            if x not in _KEYS_TO_REMOVE
        }
        return dict_with_keys_removed

    # noinspection PyMethodMayBeStatic
    def send_telemetry(self, telemetry, topic):
        """Prepares the telemetry for sending using the provided status and
        sends it.

        Parameters
        ----------
        telemetry: `dict`
            The lower level telemetry to extract the telemetry from.
        topic: SAL topic
            The SAL topic to publish the telemetry to.
        """
        # Remove some keys because they are not reported in the telemetry.
        topic.set_put(**telemetry)

    async def close_tasks(self):
        """Disconnect from the TCP/IP controller, if connected, and stop
        the mock controller, if running.
        """
        await super().close_tasks()
        await self.disconnect()

    async def configure(self, config):
        self.config = config

    async def one_status_loop(self, method, interval):
        """Run one status method forever at the specified interval.

        Parameters
        ----------
        method: coro
            The status method to run
        interval: `float`
            The interval (sec) at which to run the status method.

        """
        try:
            while True:
                await method()
                await asyncio.sleep(interval)
        except Exception:
            self.log.exception(f"one_status_loop({method}) failed")

    @property
    def connected(self):
        if None in (self.reader, self.writer):
            return False
        return True

    @staticmethod
    def get_config_pkg():
        return "ts_config_mttcs"

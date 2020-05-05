import logging

from .base_mock_status import BaseMockStatus


class MockApscsStatus(BaseMockStatus):
    """Represents the status of the Aperture Shutter Control System in simulation mode.
    """

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("MockApscsStatus")
        # variables holding the status of the mock Aperture Shutter
        self.status = "Closed"
        self.position_error = 0.0
        self.position_actual = 0.0
        self.position_cmd = 0.0
        self.drive_torque_actual = [0.0, 0.0, 0.0, 0.0]
        self.drive_torque_error = [0.0, 0.0, 0.0, 0.0]
        self.drive_torque_cmd = [0.0, 0.0, 0.0, 0.0]
        self.drive_current_actual = [0.0, 0.0, 0.0, 0.0]
        self.drive_temp_actual = [0.0, 0.0, 0.0, 0.0]
        self.resolver_head_raw = [0.0, 0.0, 0.0, 0.0]
        self.resolver_head_calibrated = [0.0, 0.0, 0.0, 0.0]
        self.power_absortion = 0.0

    async def determine_status(self):
        """Determine the status of the Lower Level Component and store it in the llc_status `dict`.
        """
        self.llc_status = {
            "status": self.status,
            "positionError": self.position_error,
            "positionActual": self.position_actual,
            "positionCmd": self.position_cmd,
            "driveTorqueActual": self.drive_torque_actual,
            "driveTorqueError": self.drive_torque_error,
            "driveTorqueCmd": self.drive_torque_cmd,
            "driveCurrentActual": self.drive_current_actual,
            "driveTempActual": self.drive_temp_actual,
            "resolverHeadRaw": self.resolver_head_raw,
            "resolverHeadCalibrated": self.resolver_head_calibrated,
            "powerAbsortion": self.power_absortion,
        }
        self.log.debug(f"apcs_state = {self.llc_status}")

    async def openShutter(self):
        """Mock opening of the shutter.
        """
        self.log.info(f"Received command 'openShutter'")
        self.status = "Open"
        self.position_actual = 90.0
        self.position_cmd = 90.0

    async def closeShutter(self):
        """Mock closing of the shutter.
        """
        self.log.info(f"Received command 'closeShutter'")
        self.status = "Closed"
        self.position_actual = 0.0
        self.position_cmd = 0.0

    async def stopShutter(self):
        """Mock stopping all motion of the shutter.
        """
        self.log.info(f"Received command 'stopShutter'")
        self.status = "Stopped"

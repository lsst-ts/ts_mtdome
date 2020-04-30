import asyncio
import logging
import math

from lsst.ts.Dome.llc_configuration_limits.amcs_configuration_limits import (
    AmcsConfigurationLimits,
)


class MockAzcsStatus:
    def __init__(self):
        self.log = logging.getLogger("MockAzcsStatus")
        self.az_limits = AmcsConfigurationLimits()
        # default values which may be overriden by calling moveAz, crawlAz of config
        self.jmax = self.az_limits.jmax
        self.amax = self.az_limits.amax
        self.vmax = self.az_limits.vmax
        # various variables holding the state of the mock AZ motion
        self.current_azimuth = 0
        self.motion_velocity = self.vmax
        self.motion_azimuth = 0
        self.motion_direction = "CW"
        self.motion = "Stopped"
        self.amcs_state = {}
        self.motion_task = None
        # Period to update the AZ motion
        self.period = 0.1

    async def start(self):
        # Start updating the status periodically
        self.log.debug("Starting")
        while True:
            self.motion_task = asyncio.create_task(self.determine_az_state())
            await asyncio.sleep(self.period)

    async def stop(self):
        self.motion_task.cancel()

    async def determine_az_state(self):
        if self.motion != "Stopped":
            azimuth_step = self.motion_velocity * self.period
            if self.motion_direction == "CW":
                self.current_azimuth = self.current_azimuth + azimuth_step
                if self.current_azimuth >= self.motion_azimuth:
                    self.current_azimuth = self.motion_azimuth
                    self.motion = "Stopped"
            else:
                self.current_azimuth = self.current_azimuth - azimuth_step
                if self.current_azimuth <= self.motion_azimuth:
                    self.current_azimuth = self.motion_azimuth
                    self.motion = "Stopped"
        self.amcs_state = {
            "status": self.motion,
            "positionError": 0.0,
            "positionActual": self.current_azimuth,
            "positionCmd": self.motion_azimuth,
            "driveTorqueActual": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveTorqueError": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveTorqueCmd": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveCurrentActual": [0.0, 0.0, 0.0, 0.0, 0.0],
            "driveTempActual": [20.0, 20.0, 20.0, 20.0, 20.0],
            "encoderHeadRaw": [0.0, 0.0, 0.0, 0.0, 0.0],
            "encoderHeadCalibrated": [0.0, 0.0, 0.0, 0.0, 0.0],
            "resolverRaw": [0.0, 0.0, 0.0, 0.0, 0.0],
            "resolverCalibrated": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
        self.log.debug(f"amcs_state = {self.amcs_state}")

    async def moveAz(self, azimuth):
        self.motion_azimuth = azimuth
        self.motion_velocity = self.vmax
        self.motion = "Moving"
        if self.motion_azimuth >= self.current_azimuth:
            self.motion_direction = "CW"
        else:
            self.motion_direction = "CCW"

    async def crawlAz(self, direction, velocity):
        self.motion_direction = direction
        self.motion_velocity = velocity
        self.motion = "Crawling"
        if self.motion_direction == "CW":
            self.motion_azimuth = math.inf
        else:
            self.motion_azimuth = -math.inf

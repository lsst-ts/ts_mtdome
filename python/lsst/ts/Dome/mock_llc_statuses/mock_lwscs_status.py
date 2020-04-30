import asyncio
import logging

from lsst.ts.Dome.llc_configuration_limits.lwscs_configuration_limits import (
    LwscsConfigurationLimits,
)


class MockLwscsStatus:
    def __init__(self):
        self.log = logging.getLogger("MockLwscsStatus")
        self.lws_limits = LwscsConfigurationLimits()
        # default values which may be overriden by calling moveEl, crawlEl of config
        self.jmax = self.lws_limits.jmax
        self.amax = self.lws_limits.amax
        self.vmax = self.lws_limits.vmax
        # various variables holding the state of the mock EL motion
        self.current_elevation = 0
        self.motion_velocity = self.vmax
        self.motion_elevation = 0
        self.motion_direction = "UP"
        self.motion = "Stopped"
        self.lwscs_state = {}
        self.motion_task = None
        # Period to update the EL motion
        self.period = 0.1

    async def start(self):
        # Start updating the status periodically
        self.log.debug("Starting")
        while True:
            self.motion_task = asyncio.create_task(self.determine_el_state())
            await asyncio.sleep(self.period)

    async def stop(self):
        self.motion_task.cancel()

    async def determine_el_state(self):
        if self.motion != "Stopped":
            elevation_step = self.motion_velocity * self.period
            if self.motion_direction == "UP":
                self.current_elevation = self.current_elevation + elevation_step
                if self.current_elevation >= self.motion_elevation:
                    self.current_elevation = self.motion_elevation
                    self.motion = "Stopped"
            else:
                self.current_elevation = self.current_elevation - elevation_step
                if self.current_elevation <= self.motion_elevation:
                    self.current_elevation = self.motion_elevation
                    self.motion = "Stopped"
        self.lwscs_state = {
            "status": self.motion,
            "positionError": 0.0,
            "positionActual": self.current_elevation,
            "positionCmd": self.motion_elevation,
            "driveTorqueActual": [0.0, 0.0, 0.0, 0.0],
            "driveTorqueError": [0.0, 0.0, 0.0, 0.0],
            "driveTorqueCmd": [0.0, 0.0, 0.0, 0.0],
            "driveCurrentActual": [0.0, 0.0, 0.0, 0.0],
            "driveTempActual": [20.0, 20.0, 20.0, 20.0],
            "resolverHeadRaw": [0.0, 0.0, 0.0, 0.0],
            "resolverHeadCalibrated": [0.0, 0.0, 0.0, 0.0],
            "powerAbsortion": 0.0,
        }
        self.log.debug(f"lwscs_state = {self.lwscs_state}")

    async def moveEl(self, elevation):
        self.motion_elevation = elevation
        self.motion_velocity = self.vmax
        self.motion = "Moving"
        if self.motion_elevation >= self.current_elevation:
            self.motion_direction = "UP"
        else:
            self.motion_direction = "DOWN"

    async def crawlEl(self, direction, velocity):
        self.motion_direction = direction
        self.motion_velocity = velocity
        self.motion = "Crawling"
        if self.motion_direction == "UP":
            self.motion_elevation = 90
        else:
            self.motion_elevation = 0

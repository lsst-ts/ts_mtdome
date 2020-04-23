from astropy import units as u
import math


configuration_limits = {
    "AMCS": {
        "jmax": {
            "description": "AMCS Maximum Jerk",
            "upper_limit": (3.0 * math.pi / 180.0) * u.rad / u.s ** 3,
        },
        "amax": {
            "description": "AMCS Maximum Acceleration",
            "upper_limit": (0.75 * math.pi / 180.0) * u.rad / u.s ** 2,
        },
        "vmax": {
            "description": "AMCS Maximum Velocity",
            "upper_limit": (1.5 * math.pi / 180.0) * u.rad / u.s,
        },
    },
    "LWSCS": {
        "jmax": {
            "description": "LWSCS Maximum Jerk",
            "upper_limit": (3.5 * math.pi / 180.0) * u.rad / u.s ** 3,
        },
        "amax": {
            "description": "LWSCS Maximum Acceleration",
            "upper_limit": (0.875 * math.pi / 180.0) * u.rad / u.s ** 2,
        },
        "vmax": {
            "description": "LWSCS Maximum Velocity",
            "upper_limit": (1.75 * math.pi / 180.0) * u.rad / u.s,
        },
    },
}

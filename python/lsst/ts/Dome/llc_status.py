from enum import Enum


class LlcStatus(Enum):
    """`Enum` with the statuses for the Lower Level components.
    """

    CLOSED = "Closed"
    CRAWLING = "Crawling"
    DISABLED = "Disabled"
    ENABLED = "Enabled"
    MOVING = "Moving"
    OPEN = "Open"
    PARKED = "Parked"
    PARKING = "Parking"
    STOPPED = "Stopped"

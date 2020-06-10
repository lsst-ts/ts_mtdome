__all__ = ["ResponseCode"]

import enum


class ResponseCode(enum.IntEnum):
    """`enum` with response codes.
    """

    OK = 0
    UNSUPPORTED_COMMAND = 2
    INCORRECT_PARAMETER = 3

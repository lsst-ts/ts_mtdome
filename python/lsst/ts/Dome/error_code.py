from enum import IntEnum


class ErrorCode(IntEnum):
    """`Enum` with error codes.
    """

    UNSUPPORTED_COMMAND = 2
    INCORRECT_PARAMETER = 3

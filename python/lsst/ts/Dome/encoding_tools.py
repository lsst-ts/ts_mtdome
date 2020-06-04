import json


def encode(st, **params):
    """Encode the given string and parameters.

    The params are treated as the value in a dict with st as key. In other words::

        {st: params}


    This method should be used for all communication with the Lower Level Components, except for returning
    their statuses.

    Parameters
    ----------
    st: `str`
        The string to encode.
    **params:
        Additional parameters to encode. This may be empty.

    Returns
    -------
        An encoded string representation of the string and parameters.
     """
    return json.dumps({st: params})


def encode_separately(st, **params):
    """Encode the given string and parameters.

    The params are treated as a separate dict next to a dict formed by st as key and an empty dict as value.
    In other words::

        {st: {}, {param1: value1, param2: value2, ...}

    This method should be used to return the status of the Lower Level Components only and should otherwise
    not be used.

    Parameters
    ----------
    st: `str`
        The string to encode.
    **params:
        Additional parameters to encode. This should not be empty but that isn't checked.

    Returns
    -------
        An encoded string representation of the string and parameters.
     """
    return json.dumps({st: {}, **params})


def decode(st):
    """Decode the given string.

    Parameters
    ----------
    st: `str`
        The string to decode.

    Returns
    -------
        A decoded Python representation of the string.
    """
    return json.loads(st)

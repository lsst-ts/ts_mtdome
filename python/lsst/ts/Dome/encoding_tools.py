import json


def encode(**params):
    """Encode the given parameters.

    The params are treated as the key, value pairs in a dict. In other words::

        {param1: value1, param2: value2, ...}


    This method should be used for all communication with the Lower Level Components.

    Parameters
    ----------
    **params:
        Additional parameters to encode. This may be empty.

    Returns
    -------
        An encoded string representation of the string and parameters.
     """
    return json.dumps({**params})


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

import unittest


def assertReply(component, lower_level_status, **kwargs):
    """Asserts that the values of the component parameter data are as expected.

    Parameters
    ----------
    component: `string`
        The name of the component to check the status of.
    lower_level_status: `dictionary`
        The contents of the status to check.
    **kwargs
        Additional keyword arguments that contain the expected values.
    """
    tc = unittest.TestCase("__init__")
    tc.assertIn(component, lower_level_status)
    for key in kwargs.keys():
        tc.assertEqual(lower_level_status[component][key], kwargs[key])


def assertTBD(component, lower_level_status):
    """Asserts that the values of the component parameter data are "TBD"
    This method will eventually disappear once the statuses of the other components contain meaningful.
    values.

    Parameters
    ----------
    component: `string`
        The name of the component to check the status of.
    lower_level_status: `dictionary`
        The contents of the status to check.
    """
    tc = unittest.TestCase("__init__")
    tc.assertIn(component, lower_level_status)
    tc.assertEqual(lower_level_status[component], "TBD")

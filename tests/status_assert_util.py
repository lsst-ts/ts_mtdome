import unittest


def assertReply(component, lower_level_status, **kwargs):
    """Asserts that the values of the component parameter data are as expected.

    Parameters
    ----------
    component : `string`
        The name of the component to check the status of.
    lower_level_status : `dictionary`
        The contents of the status to check.
    **kwargs
        Additional keyword arguments that contain the expected values.
    """
    tc = unittest.TestCase("__init__")
    tc.assertIn(component, lower_level_status)
    for key in kwargs.keys():
        # A dict here indicates a range that the valiue should be between
        if isinstance(kwargs[key], list):
            for check_value, status_value in zip(
                kwargs[key], lower_level_status[component][key]
            ):
                tc.assertEqual(check_value, status_value)
        elif isinstance(kwargs[key], dict):
            tc.assertGreaterEqual(
                lower_level_status[component][key], kwargs[key]["lower"]
            ) and tc.assertLessEqual(
                lower_level_status[component][key], kwargs[key]["upper"]
            )
        else:
            tc.assertEqual(lower_level_status[component][key], kwargs[key])

"""Applications are allowed around the clock, including weekends."""
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Asia/Yekaterinburg')


def application_time_allowed(now=None):
    """The user authorized automatic applications at every hour."""
    return True

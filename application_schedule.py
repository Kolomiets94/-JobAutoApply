"""Application hours use the candidate's timezone, including manual/delayed runs."""
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Asia/Yekaterinburg')


def application_time_allowed(now=None):
    local = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    return local.weekday() < 5 and 6 <= local.hour < 18

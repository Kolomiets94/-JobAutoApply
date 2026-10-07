"""Application time policy: daily morning/afternoon batches, including weekends."""
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Asia/Yekaterinburg')


def application_time_allowed(now=None):
    """Five two-hour batches start at 06:00 local; never start in the evening."""
    local = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    return 6 <= local.hour < 16

"""Application time policy: daily morning/afternoon batches, including weekends."""
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Asia/Yekaterinburg')


def application_time_allowed(now=None):
    """Two-hour batches run 06:00 through 16:00 local; stop at 18:00."""
    local = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    return 6 <= local.hour < 18

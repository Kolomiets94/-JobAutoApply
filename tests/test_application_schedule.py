from datetime import datetime, timezone
from application_schedule import TIMEZONE, application_time_allowed


def test_applications_allowed_every_hour_including_weekends():
    for day in range(5, 12):
        for hour in range(24):
            assert application_time_allowed(datetime(2026, 10, day, hour, tzinfo=TIMEZONE))
            assert application_time_allowed(datetime(2026, 10, day, hour, tzinfo=timezone.utc))

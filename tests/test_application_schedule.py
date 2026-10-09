from datetime import datetime
from application_schedule import TIMEZONE, application_time_allowed


def test_morning_batches_include_weekends_and_block_night():
    for day in range(5, 12):
        for hour in range(24):
            assert application_time_allowed(datetime(2026,10,day,hour,tzinfo=TIMEZONE)) == (6 <= hour < 18)

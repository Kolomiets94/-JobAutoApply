"""Pin the clock so application tests do not depend on runner time or weekday."""
from datetime import datetime as RealDatetime
import pytest
import application_schedule


@pytest.fixture(autouse=True)
def application_clock(monkeypatch):
    class FixedDatetime(RealDatetime):
        @classmethod
        def now(cls, tz=None):
            return RealDatetime(2026, 10, 7, 10, tzinfo=application_schedule.TIMEZONE).astimezone(tz)
    monkeypatch.setattr(application_schedule, 'datetime', FixedDatetime)

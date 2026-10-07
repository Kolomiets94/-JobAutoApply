from datetime import datetime, timezone
from application_schedule import TIMEZONE, application_time_allowed
from application_dispatcher import dispatch


def test_weekday_boundaries():
    def at(hour, minute=0):
        return datetime(2026, 10, 7, hour, minute, tzinfo=TIMEZONE)
    assert not application_time_allowed(at(5,59))
    assert application_time_allowed(at(6))
    assert application_time_allowed(at(17,59))
    assert not application_time_allowed(at(18))
    assert not application_time_allowed(at(23))


def test_weekends_and_utc_conversion():
    assert not application_time_allowed(datetime(2026,10,10,10,tzinfo=TIMEZONE))
    assert not application_time_allowed(datetime(2026,10,11,10,tzinfo=TIMEZONE))
    assert application_time_allowed(datetime(2026,10,7,1,tzinfo=timezone.utc))
    assert not application_time_allowed(datetime(2026,10,7,13,tzinfo=timezone.utc))


def test_manual_dispatch_cannot_bypass_window(monkeypatch):
    monkeypatch.setattr('application_dispatcher.application_time_allowed', lambda: False)
    assert dispatch({'apply_email':'jobs@example.com'}, 'hello')['reason'] == 'outside_application_hours'

from notification_rules import format_notification, should_notify


def test_should_notify_uses_default_threshold(monkeypatch):
    monkeypatch.setenv("MATCH_NOTIFY_MIN_SCORE", "70")
    assert should_notify({"match_score": 70}) is True
    assert should_notify({"match_score": 69.9}) is False


def test_should_notify_accepts_string_scores():
    assert should_notify({"match_score": "82"}, min_score="80") is True
    assert should_notify({"match_score": None}, min_score=1) is False


def test_format_notification_contains_key_fields():
    message = format_notification({
        "title": "Junior Frontend Developer",
        "source": "RemoteOK",
        "url": "https://example.com/job/1",
        "match_score": 88,
        "profit_score": 75,
        "resume_skills_match": ["React", "TypeScript"],
    })

    assert "Junior Frontend Developer" in message
    assert "RemoteOK" in message
    assert "88%" in message
    assert "React, TypeScript" in message
    assert "https://example.com/job/1" in message

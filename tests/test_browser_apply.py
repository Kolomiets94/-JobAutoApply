import json

import browser_apply


def test_hh_apply_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AUTO_BROWSER_APPLY", raising=False)
    result = browser_apply.apply_hh(
        {"url": "https://hh.ru/vacancy/123"},
        "hello",
    )
    assert result == {"status": "SHORTLISTED", "reason": "browser_apply_disabled"}


def test_non_hh_url_is_skipped(monkeypatch):
    monkeypatch.setenv("AUTO_BROWSER_APPLY", "1")
    result = browser_apply.apply_hh(
        {"url": "https://example.com/job"},
        "hello",
    )
    assert result["reason"] == "unsupported_browser_source"


def test_storage_state_from_json_secret(monkeypatch):
    state = {"cookies": [{"name": "x", "value": "1", "domain": ".hh.ru", "path": "/"}], "origins": []}
    monkeypatch.setenv("HH_STORAGE_STATE_JSON", json.dumps(state))
    assert browser_apply._storage_state() == state


def test_invalid_storage_state_json_is_ignored(monkeypatch):
    monkeypatch.setenv("HH_STORAGE_STATE_JSON", "{not-json")
    assert browser_apply._storage_state() is None

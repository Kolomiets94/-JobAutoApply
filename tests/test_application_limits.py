from unittest.mock import patch

import worker


def _lead(url="https://hh.ru/vacancy/1"):
    return {
        "source": "hh",
        "category": "frontend",
        "title": "Junior React Developer",
        "description": "React TypeScript",
        "url": url,
        "profit_score": 80,
        "eligible": True,
        "matched_skills": ["react", "typescript"],
    }


def test_skips_already_submitted_lead():
    lead = _lead()
    with patch.object(worker, "collect_all", return_value=[lead]), \
         patch.object(worker, "rank_leads", return_value=[lead]), \
         patch.object(worker, "enqueue", return_value="lead-1"), \
         patch.object(worker, "was_submitted", return_value=True), \
         patch.object(worker, "submitted_today", return_value=0), \
         patch.object(worker, "dispatch") as dispatch:
        result = worker.run()

    assert result["results"][0]["reason"] == "already_submitted"
    assert result["stats"]["duplicate_skipped"] == 1
    dispatch.assert_not_called()


def test_respects_daily_application_limit(monkeypatch):
    monkeypatch.setenv("DAILY_APPLICATION_LIMIT", "10")
    lead = _lead()
    with patch.object(worker, "collect_all", return_value=[lead]), \
         patch.object(worker, "rank_leads", return_value=[lead]), \
         patch.object(worker, "enqueue", return_value="lead-1"), \
         patch.object(worker, "was_submitted", return_value=False), \
         patch.object(worker, "submitted_today", return_value=10), \
         patch.object(worker, "dispatch") as dispatch:
        result = worker.run()

    assert result["results"][0]["reason"] == "daily_application_limit"
    assert result["stats"]["daily_limit_skipped"] == 1
    dispatch.assert_not_called()


def test_submitted_result_increments_daily_total(monkeypatch):
    monkeypatch.setenv("DAILY_APPLICATION_LIMIT", "10")
    lead = _lead()
    with patch.object(worker, "collect_all", return_value=[lead]), \
         patch.object(worker, "rank_leads", return_value=[lead]), \
         patch.object(worker, "enqueue", return_value="lead-1"), \
         patch.object(worker, "was_submitted", return_value=False), \
         patch.object(worker, "submitted_today", return_value=2), \
         patch.object(worker, "set_state"), \
         patch.object(worker, "dispatch", return_value={"status": "SUBMITTED", "reason": "browser_hh_sent"}):
        result = worker.run()

    assert result["stats"]["submitted_today_total"] == 3

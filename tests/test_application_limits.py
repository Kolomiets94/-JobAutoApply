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
    monkeypatch.setenv("DAILY_JOB_LIMIT", "10")
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
    monkeypatch.setenv("DAILY_JOB_LIMIT", "10")
    lead = _lead()
    with patch.object(worker, "collect_all", return_value=[lead]), \
         patch.object(worker, "rank_leads", return_value=[lead]), \
         patch.object(worker, "enqueue", return_value="lead-1"), \
         patch.object(worker, "was_submitted", return_value=False), \
         patch.object(worker, "submitted_today", side_effect=[2, 0]), \
         patch.object(worker, "set_state"), \
         patch.object(worker, "dispatch", return_value={"status": "SUBMITTED", "reason": "browser_hh_sent"}):
        result = worker.run()

    assert result["stats"]["submitted_today_total"] == 3


def test_full_jobs_bucket_does_not_block_freelance(monkeypatch):
    job = _lead()
    freelance = {**_lead("https://freelance.habr.com/tasks/1"), "source": "habr_freelance"}
    with patch.object(worker, "collect_all", return_value=[job, freelance]), \
         patch.object(worker, "rank_leads", return_value=[job, freelance]), \
         patch.object(worker, "enqueue", side_effect=["job-1", "freelance-1"]), \
         patch.object(worker, "was_submitted", return_value=False), \
         patch.object(worker, "submitted_today", side_effect=[10, 0]), \
         patch.object(worker, "set_state"), \
         patch.object(worker, "dispatch", return_value={"status":"SUBMITTED"}) as send:
        result = worker.run()
    assert send.call_count == 1
    assert result["stats"]["jobs_submitted_today"] == 10
    assert result["stats"]["freelance_submitted_today"] == 1


def test_full_freelance_bucket_does_not_block_jobs():
    job = _lead()
    with patch.object(worker, "collect_all", return_value=[job]), \
         patch.object(worker, "rank_leads", return_value=[job]), \
         patch.object(worker, "enqueue", return_value="job-1"), \
         patch.object(worker, "was_submitted", return_value=False), \
         patch.object(worker, "submitted_today", side_effect=[0, 10]), \
         patch.object(worker, "set_state"), \
         patch.object(worker, "dispatch", return_value={"status":"SUBMITTED"}) as send:
        result = worker.run()
    assert send.call_count == 1
    assert result["stats"]["jobs_submitted_today"] == 1
    assert result["stats"]["freelance_submitted_today"] == 10

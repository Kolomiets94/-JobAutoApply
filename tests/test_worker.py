from unittest.mock import patch

import worker


def test_collect_all_deduplicates_urls(monkeypatch):
    monkeypatch.setattr(worker, "JOB_COLLECTORS", ())
    same = {"source": "hh", "title": "React Junior", "url": "https://example.com/1"}
    other = {"source": "remoteok", "title": "Frontend", "url": "https://example.com/2"}

    with patch.object(worker, "hh_search", return_value=[same]), \
         patch.object(worker, "remoteok", return_value=[same, other]), \
         patch.object(worker, "collect_freelance", return_value=[]), \
         patch.object(worker, "collect_peopleperhour", return_value=[]), \
         patch.object(worker, "collect_prolinker", return_value=[]), \
         patch.object(worker, "collect_freelancehunt", return_value=[]):
        leads = worker.collect_all()

    urls = [lead["url"] for lead in leads]
    assert urls.count("https://example.com/1") == 1
    assert "https://example.com/2" in urls


def test_collect_all_isolates_source_failures(monkeypatch):
    monkeypatch.setattr(worker, "JOB_COLLECTORS", ())
    lead = {"source": "remoteok", "title": "React", "url": "https://example.com/ok"}

    with patch.object(worker, "hh_search", side_effect=RuntimeError("boom")), \
         patch.object(worker, "remoteok", return_value=[lead]), \
         patch.object(worker, "collect_freelance", side_effect=RuntimeError("boom")), \
         patch.object(worker, "collect_peopleperhour", return_value=[]), \
         patch.object(worker, "collect_prolinker", return_value=[]), \
         patch.object(worker, "collect_freelancehunt", return_value=[]):
        leads = worker.collect_all()

    assert leads == [lead]


def test_run_keeps_no_email_lead_for_confirmation():
    lead = {
        "source": "test",
        "category": "freelance",
        "title": "React landing page",
        "description": "React TypeScript landing page",
        "url": "https://example.com/project",
        "profit_score": 80,
        "eligible": True,
        "matched_skills": ["react", "typescript"],
    }

    with patch.object(worker, "collect_all", return_value=[lead]), \
         patch.object(worker, "rank_leads", return_value=[lead]), \
         patch.object(worker, "enqueue", return_value="lead-1"), \
         patch.object(worker, "set_state") as set_state:
        result = worker.run()

    assert result["results"][0]["status"] == "NEEDS_CONFIRMATION"
    assert result["results"][0]["reason"] == "no_free_direct_channel"
    set_state.assert_any_call("lead-1", "SHORTLISTED")
    set_state.assert_any_call("lead-1", "NEEDS_CONFIRMATION")


def test_prioritize_actionable_leads(monkeypatch):
    monkeypatch.delenv("FREELANCEHUNT_TOKEN", raising=False)
    leads = [
        {"source": "prolinker_firecrawl", "title": "React project"},
        {"source": "fl_ru", "paid_bid": True, "title": "Paid bid"},
        {"source": "hh", "title": "Junior QA"},
        {"source": "remote_job_ru", "title": "Junior frontend"},
        {"source": "jobicy", "apply_email": "jobs@example.com", "title": "Junior React"},
        {"source": "prolinker_firecrawl", "title": "Email project", "apply_email": "client@example.com"},
    ]
    prioritized = worker.prioritize_actionable_leads(leads)
    assert [x["title"] for x in prioritized] == [
        "Junior frontend", "Junior React", "React project", "Junior QA",
        "Email project", "Paid bid",
    ]


def test_freelancehunt_api_priority_requires_token(monkeypatch):
    lead = {"source": "freelancehunt", "can_api_bid": True}
    monkeypatch.delenv("FREELANCEHUNT_TOKEN", raising=False)
    assert worker._application_priority(lead) == 1
    monkeypatch.setenv("FREELANCEHUNT_TOKEN", "test")
    assert worker._application_priority(lead) == 0


def test_role_priority_is_preserved_over_channel_priority():
    leads = [
        {"source": "hh", "title": "Junior QA Engineer"},
        {"source": "hh", "title": "Junior HTML CSS верстальщик"},
        {"source": "jobicy", "title": "Junior Frontend Developer"},
        {"source": "hh", "title": "Junior React Developer"},
    ]
    result = worker.prioritize_actionable_leads(leads)
    assert [item["title"] for item in result] == [
        "Junior React Developer", "Junior Frontend Developer",
        "Junior HTML CSS верстальщик", "Junior QA Engineer",
    ]

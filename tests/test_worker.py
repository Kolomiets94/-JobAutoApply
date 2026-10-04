from unittest.mock import patch

import worker


def test_collect_all_deduplicates_urls():
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


def test_collect_all_isolates_source_failures():
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

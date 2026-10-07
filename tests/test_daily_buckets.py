from datetime import datetime, timezone
import queue_store


def test_daily_counts_separate_jobs_and_freelance(tmp_path, monkeypatch):
    monkeypatch.setattr(queue_store, 'DB_PATH', str(tmp_path / 'history.db'))
    for source in ('hh', 'habr_career', 'habr_freelance'):
        lid = queue_store.enqueue({'url': 'https://example.com/' + source, 'source': source})
        queue_store.set_state(lid, 'SUBMITTED')
    assert queue_store.submitted_today('jobs') == 2
    assert queue_store.submitted_today('freelance') == 1
    assert queue_store.submitted_today() == 3

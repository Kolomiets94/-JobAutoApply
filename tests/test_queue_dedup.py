import hashlib
import sqlite3

import queue_store as queue


def test_hh_variants_share_persistent_id():
    variants = [
        'https://hh.ru/vacancy/123',
        'https://www.hh.ru/vacancy/123?from=search',
        'https://ekaterinburg.hh.ru/vacancy/123?utm_source=test#response',
    ]
    assert len({queue.lead_id({'url': url}) for url in variants}) == 1
    assert queue.lead_id({'url': variants[0]}) != queue.lead_id({'url': 'https://hh.ru/vacancy/124'})


def test_variant_stays_submitted_after_database_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, 'DB_PATH', str(tmp_path / 'hunter.db'))
    lid = queue.enqueue({'url': 'https://hh.ru/vacancy/123?from=search'})
    queue.set_state(lid, 'SUBMITTED')
    repeated = queue.enqueue({'url': 'https://www.hh.ru/vacancy/123?from=another'})
    assert repeated == lid
    assert queue.was_submitted(repeated)
    assert len(queue.list_queue()) == 1


def test_legacy_history_blocks_new_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, 'DB_PATH', str(tmp_path / 'hunter.db'))
    queue.enqueue({'url': 'https://hh.ru/vacancy/999'})
    url = 'https://hh.ru/vacancy/123?from=old'
    old_id = hashlib.sha256(url.encode()).hexdigest()
    with sqlite3.connect(queue.DB_PATH) as db:
        db.execute('INSERT INTO leads (id,url,state) VALUES (?,?,?)', (old_id, url, 'SUBMITTED'))
    new_id = queue.enqueue({'url': 'https://www.hh.ru/vacancy/123'})
    assert queue.was_submitted(new_id)
    assert not queue.was_submitted(queue.lead_id({'url': 'https://hh.ru/vacancy/999'}))


def test_unrelated_host_is_not_hh():
    a = {'url': 'https://hh.ru/vacancy/123'}
    b = {'url': 'https://hh.ru.example.org/vacancy/123'}
    assert queue.lead_id(a) != queue.lead_id(b)

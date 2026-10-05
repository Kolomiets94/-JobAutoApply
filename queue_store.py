"""Persistent lead queue using SQLite."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("HUNTER_DB", "hunter.db")
STATES = (
    "FOUND", "SHORTLISTED", "APPLYING", "SUBMITTED", "NEEDS_CONFIRMATION",
    "REPLIED", "WON", "SKIPPED", "FAILED", "NEEDS_HUMAN",
)


def _db():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS leads(
      id TEXT PRIMARY KEY, url TEXT, source TEXT, title TEXT, state TEXT,
      score INTEGER DEFAULT 0, payload TEXT, updated_at TEXT)""")
    c.commit()
    return c


def lead_id(lead):
    raw = lead.get("url") or json.dumps(lead, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def enqueue(lead):
    lid = lead_id(lead)
    now = datetime.now(timezone.utc).isoformat()
    with _db() as c:
        c.execute("""INSERT OR IGNORE INTO leads
        (id,url,source,title,state,score,payload,updated_at)
        VALUES(?,?,?,?,?,?,?,?)""", (
            lid, lead.get("url"), lead.get("source"), lead.get("title"),
            "FOUND", int(lead.get("profit_score", 0)),
            json.dumps(lead, ensure_ascii=False), now,
        ))
    return lid


def set_state(lid, state):
    if state not in STATES:
        raise ValueError("invalid state")
    with _db() as c:
        c.execute(
            "UPDATE leads SET state=?,updated_at=? WHERE id=?",
            (state, datetime.now(timezone.utc).isoformat(), lid),
        )


def get_state(lid):
    with _db() as c:
        row = c.execute("SELECT state FROM leads WHERE id=?", (lid,)).fetchone()
    return row[0] if row else None


def was_submitted(lid):
    return get_state(lid) in ("SUBMITTED", "REPLIED", "WON")


def submitted_today():
    today = datetime.now(timezone.utc).date().isoformat()
    with _db() as c:
        row = c.execute(
            """SELECT COUNT(*) FROM leads
               WHERE state IN ('SUBMITTED','REPLIED','WON')
               AND substr(updated_at,1,10)=?""",
            (today,),
        ).fetchone()
    return int(row[0] if row else 0)


def list_queue(limit=100):
    with _db() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM leads ORDER BY score DESC,updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(x) for x in rows]

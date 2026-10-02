"""Persistent lead queue using SQLite.

States: FOUND -> SHORTLISTED -> APPLYING -> SUBMITTED -> REPLIED -> WON.
A blocked form can be marked NEEDS_CONFIRMIRMATION without stopping other leads.
"""
import json, os, sqlite3, hashlib
from datetime import datetime, timezone

DB_PATH=os.getenv("HUNTER_DB","hunter.db")
STATES=("FOUND","SHORTLISTED","APPLYING","SUBMITTED","NEEDS_CONFIRMATION","REPLIED","WON","SKIPPED","FAILED")

def _db():
    c=sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS leads(
      id TEXT PRIMARY KEY, url TEXT, source TEXT, title TEXT, state TEXT,
      score INTEGER DEFAULT 0, payload TEXT, updated_at TEXT)""")
    c.commit()
    return c

def lead_id(lead):
    raw=lead.get("url") or json.dumps(lead,sort_keys=True,ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def enqueue(lead):
    lid=lead_id(lead); now=datetime.now(timezone.utc).isoformat()
    with _db() as c:
        c.execute("""INSERT OR IGNORE INTO leads
        (id,url,source,title,state,score,payload,updated_at)
        VALUES(?,?,?,?,?,?,?,?)""",(lid,lead.get("url"),lead.get("source"),
        lead.get("title"),"FOUND",int(lead.get("profit_score",0)),
        json.dumps(lead,ensure_ascii=False),now))
    return lid

def set_state(lid,state):
    if state not in STATES: raise ValueError("invalid state")
    with _db() as c:
        c.execute("UPDATE leads SET state=?,updated_at=? WHERE id=?",
                  (state,datetime.now(timezone.utc).isoformat(),lid))

def list_queue(limit=100):
    with _db() as c:
        c.row_factory=sqlite3.Row
        rows=c.execute("SELECT * FROM leads ORDER BY score DESC,updated_at DESC LIMIT ?",(limit,)).fetchall()
    return [dict(x) for x in rows]

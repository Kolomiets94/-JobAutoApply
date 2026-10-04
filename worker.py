"""Unified one-pass job + freelance hunter worker.

Collects job-board vacancies and freelance projects, ranks them with the same
transparent scoring pipeline, stores them in SQLite, prepares proposals, and
dispatches only through explicitly configured free channels.
"""
from main import QUERIES, hh_search, remoteok
from freelance_sources import (
    collect_freelance,
    collect_peopleperhour,
    collect_prolinker,
)
from freelancehunt_adapter import collect_freelancehunt
from profit_ranker import rank_leads
from proposal_writer import make_proposal
from application_dispatcher import dispatch
from queue_store import enqueue, set_state


def collect_all():
    """Collect public job and freelance leads without letting one source stop the run."""
    leads = []

    # Job boards
    for tag, query in QUERIES:
        try:
            leads += hh_search(tag, query)
        except Exception:
            pass

    try:
        leads += remoteok()
    except Exception:
        pass

    # Freelance sources
    try:
        leads += collect_freelance()
    except Exception:
        pass

    try:
        leads += collect_peopleperhour()
    except Exception:
        pass

    try:
        leads += collect_prolinker()
    except Exception:
        pass

    try:
        leads += collect_freelancehunt()
    except Exception:
        pass

    # Deduplicate by URL while preserving first occurrence.
    seen = set()
    unique = []
    for lead in leads:
        key = lead.get("url") or str(lead)
        if key in seen:
            continue
        seen.add(key)
        unique.append(lead)
    return unique


def run():
    leads = collect_all()
    ranked = rank_leads(leads)

    stats = {
        "found": len(leads),
        "ranked": len(ranked),
        "submitted": 0,
        "shortlisted": 0,
        "needs_confirmation": 0,
        "skipped": 0,
        "failed": 0,
    }
    results = []

    for lead in ranked:
        lid = enqueue(lead)
        try:
            set_state(lid, "SHORTLISTED")
            proposal = make_proposal(lead)
            result = dispatch(lead, proposal)
            state = result["status"]
            set_state(lid, state)

            key = state.lower()
            if key in stats:
                stats[key] += 1

            results.append(
                {
                    "id": lid,
                    "title": lead.get("title"),
                    "source": lead.get("source"),
                    "url": lead.get("url"),
                    "score": lead.get("profit_score"),
                    "matched_skills": lead.get("matched_skills", []),
                    "proposal": proposal,
                    **result,
                }
            )
        except Exception as exc:
            set_state(lid, "FAILED")
            stats["failed"] += 1
            results.append(
                {
                    "id": lid,
                    "title": lead.get("title"),
                    "status": "FAILED",
                    "reason": type(exc).__name__,
                }
            )

    return {"stats": stats, "results": results}


if __name__ == "__main__":
    import json

    print(json.dumps(run(), ensure_ascii=False, indent=2))

"""Unified one-pass job + freelance hunter worker."""

import os

from main import QUERIES, hh_search, remoteok
from freelance_sources import collect_freelance, collect_peopleperhour, collect_prolinker
from freelancehunt_adapter import collect_freelancehunt
from job_matcher import JobMatcher
from profit_ranker import rank_leads
from proposal_writer import make_proposal
from application_dispatcher import dispatch
from queue_store import enqueue, set_state
from notification_rules import format_notification, should_notify


def load_resume_text():
    """Load resume text from env first, then an optional local file."""
    text = os.getenv("RESUME_TEXT", "").strip()
    if text:
        return text

    path = os.getenv("RESUME_FILE", "resume/profile.txt")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def collect_all():
    """Collect public job and freelance leads without letting one source stop the run."""
    leads = []

    for tag, query in QUERIES:
        try:
            leads += hh_search(tag, query)
        except Exception:
            pass

    for collector in (
        remoteok,
        collect_freelance,
        collect_peopleperhour,
        collect_prolinker,
        collect_freelancehunt,
    ):
        try:
            leads += collector()
        except Exception:
            pass

    seen = set()
    unique = []
    for lead in leads:
        key = lead.get("url") or str(lead)
        if key in seen:
            continue
        seen.add(key)
        unique.append(lead)
    return unique


def apply_resume_matching(leads, resume_text=None):
    """Attach deterministic resume-match metadata before profitability ranking."""
    resume_text = load_resume_text() if resume_text is None else resume_text
    if not resume_text:
        return leads

    matcher = JobMatcher()
    return [matcher.score_lead(lead, resume_text) for lead in leads]


def run():
    leads = apply_resume_matching(collect_all())
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
    notifications = []

    for lead in ranked:
        if should_notify(lead):
            notifications.append({
                "title": lead.get("title"),
                "source": lead.get("source"),
                "url": lead.get("url"),
                "match_score": lead.get("match_score"),
                "message": format_notification(lead),
            })
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

            results.append({
                "id": lid,
                "title": lead.get("title"),
                "source": lead.get("source"),
                "url": lead.get("url"),
                "score": lead.get("profit_score"),
                "match_score": lead.get("match_score"),
                "match_reason": lead.get("match_reason"),
                "resume_skills_match": lead.get("resume_skills_match", []),
                "matched_skills": lead.get("matched_skills", []),
                "proposal": proposal,
                **result,
            })
        except Exception as exc:
            set_state(lid, "FAILED")
            stats["failed"] += 1
            results.append({
                "id": lid,
                "title": lead.get("title"),
                "status": "FAILED",
                "reason": type(exc).__name__,
            })

    stats["notifications"] = len(notifications)
    return {"stats": stats, "results": results, "notifications": notifications}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))

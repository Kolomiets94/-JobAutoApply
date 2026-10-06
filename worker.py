"""Unified one-pass job + freelance hunter worker."""

import os

from main import QUERIES, hh_search, remoteok
from freelance_sources import collect_freelance, collect_peopleperhour, collect_prolinker
from freelancehunt_adapter import collect_freelancehunt
from job_matcher import JobMatcher
from profit_ranker import rank_leads
from proposal_writer import make_proposal
from application_dispatcher import dispatch
from queue_store import enqueue, get_state, set_state, submitted_today, was_submitted
from notification_rules import format_notification, should_notify
from telegram_notifier import send_message, send_notification


def load_resume_text():
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
    resume_text = load_resume_text() if resume_text is None else resume_text
    if not resume_text:
        return leads
    matcher = JobMatcher()
    return [matcher.score_lead(lead, resume_text) for lead in leads]


def deliver_notifications(notifications):
    deliveries = []
    for notification in notifications:
        try:
            deliveries.append({
                "title": notification.get("title"),
                **send_notification(notification),
            })
        except Exception as exc:
            deliveries.append({
                "title": notification.get("title"),
                "status": "FAILED",
                "reason": type(exc).__name__,
            })
    return deliveries


def run():
    leads = apply_resume_matching(collect_all())
    ranked = rank_leads(leads)

    daily_limit = int(os.getenv("DAILY_APPLICATION_LIMIT", "10"))
    submitted_count = submitted_today()
    per_run_limit = int(os.getenv("HOURLY_APPLICATION_LIMIT", "2"))

    stats = {
        "found": len(leads),
        "ranked": len(ranked),
        "submitted": 0,
        "shortlisted": 0,
        "needs_confirmation": 0,
        "skipped": 0,
        "failed": 0,
        "duplicate_skipped": 0,
        "daily_limit_skipped": 0,
    }
    results = []
    notifications = []

    for lead in ranked:
        if stats["submitted"] >= per_run_limit:
            break

        lid = enqueue(lead)

        if was_submitted(lid):
            stats["duplicate_skipped"] += 1
            results.append({
                "id": lid,
                "title": lead.get("title"),
                "status": "SKIPPED",
                "reason": "already_submitted",
            })
            continue

        if submitted_count >= daily_limit:
            stats["daily_limit_skipped"] += 1
            results.append({
                "id": lid,
                "title": lead.get("title"),
                "status": "SKIPPED",
                "reason": "daily_application_limit",
            })
            continue

        if should_notify(lead):
            notifications.append({
                "title": lead.get("title"),
                "source": lead.get("source"),
                "url": lead.get("url"),
                "match_score": lead.get("match_score"),
                "message": format_notification(lead),
            })

        try:
            set_state(lid, "SHORTLISTED")
            proposal = make_proposal(lead)
            result = dispatch(lead, proposal)
            state = result["status"]
            set_state(lid, state)

            if state == "SUBMITTED":
                submitted_count += 1

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

    deliveries = deliver_notifications(notifications)
    stats["notifications"] = len(notifications)
    stats["notifications_sent"] = sum(
        1 for item in deliveries if item.get("status") == "SENT"
    )
    stats["daily_application_limit"] = daily_limit
    stats["hourly_application_limit"] = per_run_limit
    stats["submitted_today_total"] = submitted_count

    summary_message = (
        "Job Auto Apply report\n"
        f"Found: {stats['found']}\n"
        f"Ranked: {stats['ranked']}\n"
        f"Submitted this run: {stats['submitted']}\n"
        f"Skipped: {stats['skipped'] + stats['duplicate_skipped'] + stats['daily_limit_skipped']}\n"
        f"Failed: {stats['failed']}\n"
        f"Telegram vacancy alerts sent: {stats['notifications_sent']}\n"
        f"Submitted today: {stats['submitted_today_total']}/{stats['daily_application_limit']}"
    )
    try:
        summary_delivery = send_message(summary_message)
    except Exception as exc:
        summary_delivery = {
            "status": "FAILED",
            "reason": type(exc).__name__,
        }

    return {
        "stats": stats,
        "results": results,
        "notifications": notifications,
        "notification_deliveries": deliveries,
        "summary_delivery": summary_delivery,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))

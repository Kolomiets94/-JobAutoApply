"""Unified one-pass job + freelance hunter worker."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from job_sources import JOB_COLLECTORS

from main import QUERIES, hh_search, remoteok
from freelance_sources import collect_freelance, collect_peopleperhour, collect_prolinker
from freelancehunt_adapter import collect_freelancehunt
from job_matcher import JobMatcher
from profit_ranker import rank_leads, FREELANCE_SOURCES
from proposal_writer import make_proposal
from application_schedule import application_time_allowed
from application_dispatcher import dispatch
from queue_store import enqueue, set_state, submitted_today, was_submitted
from notification_rules import format_notification, should_notify
from telegram_notifier import send_message, send_notification

DEFAULT_RESUME_TEXT = """Junior Frontend Developer. React, TypeScript, JavaScript ES6+, Redux Toolkit, React Router, REST API, HTML5, CSS3, SCSS, Git, Figma, Vite, Webpack, responsive and cross-browser layout. Projects include authentication, protected routes, CRUD, API integration, debounce search, validation and error handling. Manual testing of own web applications. English B1. Remote work."""


def load_resume_text():
    text = os.getenv("RESUME_TEXT", "").strip()
    if text:
        return text
    path = os.getenv("RESUME_FILE", "resume/profile.txt")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return DEFAULT_RESUME_TEXT


COLLECTION_ERRORS = []


def _lead_key(lead):
    """Canonicalize HH URLs so the same vacancy found by several queries is processed once."""
    url = str(lead.get("url") or "")
    match = __import__("re").search(r"https?://(?:www\.)?hh\.ru/vacancy/(\d+)", url)
    if match:
        return f"hh:{match.group(1)}"
    if url:
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_") and k not in ("ref", "source")]
        return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))
    return str(lead)


def record_collection_error(source, exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    reason = type(exc).__name__ + (f" HTTP {status}" if status else "")
    COLLECTION_ERRORS.append({"source": source, "reason": reason})
    print(f"[collector] {source}: {reason}", flush=True)


def collect_all():
    COLLECTION_ERRORS.clear()
    leads = []
    for tag, query in QUERIES:
        try:
            leads += hh_search(tag, query)
        except Exception as exc:
            record_collection_error("hh", exc)

    for source, collector in (
        ("remoteok", remoteok),
        ("freelance", collect_freelance),
        ("peopleperhour", collect_peopleperhour),
        ("prolinker", collect_prolinker),
        ("freelancehunt", collect_freelancehunt),
    ):
        try:
            leads += collector()
        except Exception as exc:
            record_collection_error(source, exc)

    # Independent public sources run concurrently with bounded request timeouts.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(collector): source for source, collector in JOB_COLLECTORS}
        for future in as_completed(futures):
            source = futures[future]
            try:
                collected = future.result()
                leads.extend(collected)
                print(f"[collector] {source}: {len(collected)} leads", flush=True)
            except Exception as exc:
                record_collection_error(source, exc)

    seen = set()
    unique = []
    for lead in leads:
        key = _lead_key(lead)
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


def is_freelance(lead):
    return str(lead.get("source") or "").lower() in FREELANCE_SOURCES


def _application_priority(lead):
    """Prefer channels the dispatcher can actually submit through.

    Unknown external forms stay visible for review, but cannot crowd out
    email, HH, Remote-job or configured Freelancehunt API applications.
    """
    if lead.get("paid_bid") is True:
        return 2
    if lead.get("apply_email") or str(lead.get("apply_url") or "").lower().startswith("mailto:"):
        return 0
    source = str(lead.get("source") or "").lower()
    if source in ("hh", "remote_job_ru"):
        return 0
    if source == "freelancehunt" and lead.get("can_api_bid") and os.getenv("FREELANCEHUNT_TOKEN"):
        return 0
    return 1


def prioritize_actionable_leads(ranked):
    """Stable order: submit-capable sources first, preserve fit within tiers."""
    return sorted(ranked, key=_application_priority)


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
    if not application_time_allowed():
        message = ("Job Auto Apply: запуск вне окна откликов. "
                   "Поиск и отправка откликов выполняются в 06:00, 08:00, "
                   "10:00, 12:00 и 14:00 по Екатеринбургу.")
        try:
            delivery = send_message(message)
        except Exception as exc:
            delivery = {"status": "FAILED", "reason": type(exc).__name__}
        print(f"[telegram] off-hours report: {delivery}", flush=True)
        return {"stats": {"submitted": 0}, "results": [],
                "summary_delivery": delivery,
                "reason": "outside_application_hours",
                "application_window": "Daily batches 06:00,08:00,10:00,12:00,14:00 Asia/Yekaterinburg"}
    try:
        started = send_message("Job Auto Apply: поиск вакансий и заказов запущен.")
    except Exception as exc:
        started = {"status": "FAILED", "reason": type(exc).__name__}
    print(f"[telegram] start notification: {started}", flush=True)
    leads = apply_resume_matching(collect_all())
    if os.getenv("HUNTER_HH_ONLY", "0") == "1":
        leads = [lead for lead in leads if str(lead.get("source") or "").lower() == "hh"]
    ranked = prioritize_actionable_leads(rank_leads(leads))

    daily_limits = {
        "jobs_submitted": int(os.getenv("DAILY_JOB_LIMIT", "10")),
        "freelance_submitted": int(os.getenv("DAILY_FREELANCE_LIMIT", "10")),
    }
    daily_counts = {"jobs_submitted": submitted_today("jobs"),
                    "freelance_submitted": submitted_today("freelance")}
    daily_limit = sum(daily_limits.values())
    submitted_count = sum(daily_counts.values())
    job_limit = int(os.getenv("HOURLY_JOB_LIMIT", "2"))
    freelance_limit = int(os.getenv("HOURLY_FREELANCE_LIMIT", "2"))

    source_counts = {name: 0 for name, _ in JOB_COLLECTORS}
    for lead in leads:
        source = str(lead.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1

    stats = {
        "source_counts": source_counts,
        "collection_errors": list(COLLECTION_ERRORS),
        "resume_configured": bool(load_resume_text()),
        "found": len(leads),
        "ranked": len(ranked),
        "submitted": 0,
        "jobs_submitted": 0,
        "freelance_submitted": 0,
        "shortlisted": 0,
        "needs_confirmation": 0,
        "skipped": 0,
        "failed": 0,
        "duplicate_skipped": 0,
        "daily_limit_skipped": 0,
        "hourly_limit_skipped": 0,
    }
    results = []
    notifications = []

    for lead in ranked:
        freelance = is_freelance(lead)
        bucket = "freelance_submitted" if freelance else "jobs_submitted"
        bucket_limit = freelance_limit if freelance else job_limit

        # Do not stop the whole run when one category is full:
        # jobs and freelance have independent hourly limits.
        if stats[bucket] >= bucket_limit:
            stats["hourly_limit_skipped"] += 1
            continue

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

        if daily_counts[bucket] >= daily_limits[bucket]:
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
                daily_counts[bucket] += 1
                stats["submitted"] += 1
                stats[bucket] += 1
            else:
                key = state.lower()
                if key in stats:
                    stats[key] += 1
                else:
                    stats["skipped"] += 1

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
    stats["hourly_job_limit"] = job_limit
    stats["hourly_freelance_limit"] = freelance_limit
    stats["submitted_today_total"] = submitted_count
    stats["jobs_submitted_today"] = daily_counts["jobs_submitted"]
    stats["freelance_submitted_today"] = daily_counts["freelance_submitted"]
    stats["daily_job_limit"] = daily_limits["jobs_submitted"]
    stats["daily_freelance_limit"] = daily_limits["freelance_submitted"]

    detail_lines = []
    for item in results[:8]:
        title = str(item.get("title") or "Untitled")[:80]
        source = str(item.get("source") or "?")
        status = str(item.get("status") or "?")
        reason = str(item.get("reason") or "")
        url = str(item.get("url") or "")
        detail_lines.append(f"- {title} [{source}] — {status}" + (f" ({reason})" if reason else ""))
        if url:
            detail_lines.append(url)

    summary_message = (
        ("Job Auto Apply — HH verification report\n" if os.getenv("HUNTER_HH_ONLY", "0") == "1" else "Job Auto Apply report\n") +
        f"Found: {stats['found']}\n"
        f"Ranked: {stats['ranked']}\n"
        f"Jobs submitted this run: {stats['jobs_submitted']}/{stats['hourly_job_limit']}\n"
        f"Freelance submitted this run: {stats['freelance_submitted']}/{stats['hourly_freelance_limit']}\n"
        f"Submitted this run total: {stats['submitted']}\n"
        f"Skipped: {stats['skipped'] + stats['duplicate_skipped'] + stats['daily_limit_skipped'] + stats['hourly_limit_skipped']}\n"
        f"Failed: {stats['failed']}\n"
        f"Shortlisted (not sent): {stats['shortlisted']}\n"
        f"Needs confirmation: {stats['needs_confirmation']}\n"
        f"Telegram vacancy alerts sent: {stats['notifications_sent']}\n"
        f"Jobs submitted today: {stats['jobs_submitted_today']}/{stats['daily_job_limit']}\n"
        f"Freelance submitted today: {stats['freelance_submitted_today']}/{stats['daily_freelance_limit']}\n\n"
        "Results:\n" + ("\n".join(detail_lines) if detail_lines else "No ranked results")
    )
    summary_message += "\n\nSources: " + ", ".join(f"{name}: {count}" for name, count in source_counts.items())
    if COLLECTION_ERRORS:
        summary_message += "\nSource errors: " + "; ".join(f"{item['source']}: {item['reason']}" for item in COLLECTION_ERRORS)
    if not stats["resume_configured"]:
        summary_message += "\nResume matching: not configured"
    try:
        summary_delivery = send_message(summary_message)
    except Exception as exc:
        summary_delivery = {
            "status": "FAILED",
            "reason": type(exc).__name__,
        }

    print(f"[telegram] summary delivery: {summary_delivery}", flush=True)
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

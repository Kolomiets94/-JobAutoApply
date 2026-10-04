"""Rules and formatting for high-match notifications."""

import os


def _score(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def should_notify(lead, min_score=None):
    """Return True when a lead clears the configured resume-match threshold."""
    if min_score is None:
        min_score = os.getenv("MATCH_NOTIFY_MIN_SCORE", "70")
    return _score(lead.get("match_score")) >= _score(min_score)


def format_notification(lead):
    """Build a compact notification message for a ranked lead."""
    title = lead.get("title") or "Без названия"
    source = lead.get("source") or "unknown"
    url = lead.get("url") or ""
    match_score = _score(lead.get("match_score"))
    profit_score = _score(lead.get("profit_score"))
    skills = lead.get("resume_skills_match") or lead.get("matched_skills") or []
    skill_text = ", ".join(map(str, skills[:8])) if skills else "—"

    lines = [
        "🎯 Сильное совпадение",
        title,
        f"Источник: {source}",
        f"Совпадение: {match_score:.0f}%",
        f"Приоритет: {profit_score:.0f}",
        f"Навыки: {skill_text}",
    ]
    if url:
        lines.append(url)
    return "\n".join(lines)

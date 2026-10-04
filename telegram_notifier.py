"""Telegram delivery for top-ranked leads.

Configuration is entirely via environment variables:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

If either variable is absent, sending is disabled and the worker continues normally.
"""

import os
from typing import Dict

import requests


def is_configured() -> bool:
    return bool(
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        and os.getenv("TELEGRAM_CHAT_ID", "").strip()
    )


def send_message(text: str, timeout: int = 10) -> Dict[str, str]:
    """Send a plain-text Telegram message, or return DISABLED if not configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return {"status": "DISABLED", "reason": "telegram_not_configured"}

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return {"status": "SENT"}


def send_notification(notification: Dict, timeout: int = 10) -> Dict[str, str]:
    return send_message(notification.get("message", ""), timeout=timeout)

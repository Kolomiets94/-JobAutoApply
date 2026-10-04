"""Application dispatcher.

Uses free direct email when configured, otherwise supported browser automation.
Paid bids and security challenges are never silently accepted or bypassed.
"""

import os
import smtplib
from email.message import EmailMessage

from browser_apply import dispatch_browser


def _send_email(lead, proposal):
    email = lead.get("apply_email")
    if not email:
        return None

    if os.getenv("AUTO_SEND_EMAIL", "0") != "1":
        return {"status": "SHORTLISTED", "reason": "email_send_disabled"}

    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not all((host, user, password)):
        return {"status": "SHORTLISTED", "reason": "smtp_not_configured"}

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = email
    msg["Subject"] = f"Отклик: {lead.get('title', 'проект')}"
    msg.set_content(proposal)

    with smtplib.SMTP_SSL(
        host,
        int(os.getenv("SMTP_PORT", "465")),
        timeout=30,
    ) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)

    return {"status": "SUBMITTED", "reason": "email_sent"}


def dispatch(lead, proposal):
    if lead.get("paid_bid") is True:
        return {"status": "SKIPPED", "reason": "paid_bid"}

    email_result = _send_email(lead, proposal)
    if email_result is not None:
        return email_result

    browser_result = dispatch_browser(lead, proposal)
    if browser_result.get("reason") != "unsupported_browser_source":
        return browser_result

    return {"status": "NEEDS_CONFIRMATION", "reason": "no_free_direct_channel"}

"""Browser-based application automation.

Currently supports hh.ru vacancy pages.
The module never bypasses CAPTCHA, 2FA, login challenges, or paid actions.
Actual submission requires AUTO_BROWSER_APPLY=1.
"""

import base64
import gzip
import io
import json
import os
import re
from typing import Dict

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


HH_HOSTS = ("hh.ru", "www.hh.ru")


def _enabled() -> bool:
    return os.getenv("AUTO_BROWSER_APPLY", "0") == "1"


def _looks_like_challenge(page) -> bool:
    text = (page.locator("body").inner_text(timeout=5000) or "").lower()
    markers = (
        "captcha",
        "капча",
        "подтвердите, что вы человек",
        "проверка безопасности",
        "verify your identity",
        "security check",
        "two-factor",
        "2fa",
        "код подтверждения",
    )
    return any(marker in text for marker in markers)


def _storage_state(storage_state=None):
    if storage_state:
        return storage_state

    raw_json = os.getenv("HH_STORAGE_STATE_JSON", "").strip()
    if raw_json:
        try:
            if raw_json.startswith("gzip-base64:"):
                encoded = raw_json.removeprefix("gzip-base64:")
                compressed = base64.b64decode(encoded, validate=True)
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                    payload = stream.read(5 * 1024 * 1024 + 1)
                if len(payload) > 5 * 1024 * 1024:
                    raise ValueError("HH session exceeds decompressed size limit")
                return json.loads(payload)
            return json.loads(raw_json)
        except (ValueError, OSError, EOFError):
            return None

    path = os.getenv("HH_STORAGE_STATE", "").strip()
    return path or None


def _select_resume(page, category):
    patterns = {
        "frontend": r"frontend|front.end|фронт|react",
        "layout": r"верст|вёрст|html.?css",
        "qa": r"тестиров|\\bqa\\b|tester",
    }
    pattern = re.compile(patterns.get(category, r"(?!)"), re.I)
    radios = page.get_by_role("radio")
    if not radios.count():
        return False
    matched = page.get_by_role("radio", name=pattern)
    if not matched.count():
        return False
    matched.first.check(timeout=10000)
    return matched.first.is_checked()


def apply_hh(lead: Dict, proposal: str, storage_state=None) -> Dict[str, str]:
    """Open an hh.ru vacancy, click Respond and submit when possible."""
    url = str(lead.get("url") or "")
    if not url:
        return {"status": "SKIPPED", "reason": "missing_url"}

    if not any(host in url for host in HH_HOSTS):
        return {"status": "SKIPPED", "reason": "unsupported_browser_source"}

    if not _enabled():
        return {"status": "SHORTLISTED", "reason": "browser_apply_disabled"}

    browser_state = _storage_state(storage_state)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("BROWSER_HEADLESS", "1") != "0")
        try:
            context_kwargs = {}
            if browser_state:
                context_kwargs["storage_state"] = browser_state
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            respond = page.get_by_text("Откликнуться", exact=True)
            if respond.count() == 0:
                respond = page.locator('[data-qa="vacancy-response-link-top"]')

            if respond.count() == 0:
                body = (page.locator("body").inner_text(timeout=5000) or "").lower()
                if "войти" in body or "авториз" in body:
                    return {"status": "NEEDS_HUMAN", "reason": "login_required"}
                return {"status": "SKIPPED", "reason": "respond_button_not_found"}

            respond.first.click(timeout=10000)
            page.wait_for_timeout(1200)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            if not _select_resume(page, str(lead.get("category") or "frontend")):
                return {"status": "NEEDS_CONFIRMATION", "reason": "matching_resume_selector_not_found"}

            textarea = page.locator("textarea")
            if not textarea.count():
                return {"status": "NEEDS_CONFIRMATION", "reason": "cover_letter_field_not_found"}
            if proposal:
                textarea.first.fill(proposal)

            submit = page.get_by_text("Отправить", exact=True)
            if submit.count() == 0:
                submit = page.get_by_text("Откликнуться", exact=True)

            if submit.count() > 0:
                submit.first.click(timeout=10000)
                page.wait_for_timeout(1200)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            body = (page.locator("body").inner_text(timeout=5000) or "").lower()
            success_markers = (
                "вы откликнулись",
                "отклик отправлен",
                "резюме доставлено",
                "application sent",
            )
            if any(marker in body for marker in success_markers):
                return {"status": "SUBMITTED", "reason": "browser_hh_sent"}

            return {"status": "NEEDS_CONFIRMATION", "reason": "submission_not_confirmed"}

        except PlaywrightTimeoutError:
            return {"status": "FAILED", "reason": "browser_timeout"}
        finally:
            browser.close()


def dispatch_browser(lead: Dict, proposal: str) -> Dict[str, str]:
    source = str(lead.get("source") or lead.get("site") or "").lower()
    url = str(lead.get("url") or "").lower()

    if "hh" in source or "hh.ru" in url:
        return apply_hh(lead, proposal)

    return {"status": "SKIPPED", "reason": "unsupported_browser_source"}

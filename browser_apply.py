"""Browser-based application automation.

Currently supports hh.ru vacancy pages.
The module never bypasses CAPTCHA, 2FA, login challenges, employer questions, or paid actions.
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
RESUME_PATTERNS = {
    "frontend": re.compile(r"frontend|front[ -]?end|фронт|react", re.I),
    "layout": re.compile(r"верст|вёрст|html\s*/?\s*css", re.I),
    "qa": re.compile(r"junior\s+qa|qa\s+engineer|тестиров", re.I),
}


def _enabled() -> bool:
    return os.getenv("AUTO_BROWSER_APPLY", "0") == "1"


def _looks_like_challenge(page) -> bool:
    text = (page.locator("body").inner_text(timeout=5000) or "").lower()
    markers = (
        "captcha", "капча", "подтвердите, что вы человек", "проверка безопасности",
        "verify your identity", "security check", "two-factor", "2fa", "код подтверждения",
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


def _visible(locator) -> bool:
    try:
        return locator.is_visible(timeout=500)
    except Exception:
        return False


def _select_resume(page, category: str) -> bool:
    """Select only a resume whose visible title matches the vacancy category."""
    pattern = RESUME_PATTERNS.get(category)
    if not pattern:
        return False

    # HH sometimes hides the resume list behind a chooser.
    for label in ("Выбрать другое резюме", "Сменить резюме", "Выбрать резюме"):
        chooser = page.get_by_text(label, exact=False)
        if chooser.count() and _visible(chooser.first):
            try:
                chooser.first.click(timeout=5000)
                page.wait_for_timeout(500)
            except Exception:
                pass
            break

    # Preferred path: accessible radio controls.
    radios = page.get_by_role("radio")
    for i in range(radios.count()):
        radio = radios.nth(i)
        try:
            name = radio.get_attribute("aria-label") or ""
            if not name:
                rid = radio.get_attribute("id")
                if rid:
                    lab = page.locator(f'label[for="{rid}"]')
                    if lab.count():
                        name = lab.first.inner_text(timeout=1000)
            if pattern.search(name):
                radio.check(timeout=5000)
                return radio.is_checked()
        except Exception:
            continue

    # HH also renders resume choices as cards/links/buttons rather than radios.
    candidates = page.locator('[data-qa*="resume"], a, button, label')
    for i in range(min(candidates.count(), 250)):
        node = candidates.nth(i)
        try:
            if not _visible(node):
                continue
            text = (node.inner_text(timeout=500) or "").strip()
            if not text or not pattern.search(text):
                continue
            # Avoid clicking generic navigation that merely mentions all resumes.
            if len(text) > 220 or re.search(r"мои резюме|создать резюме", text, re.I):
                continue
            node.click(timeout=5000)
            page.wait_for_timeout(500)
            return True
        except Exception:
            continue

    # A single already-selected resume can be displayed as plain text.
    body = page.locator("body").inner_text(timeout=5000) or ""
    matches = [p for p in RESUME_PATTERNS.values() if p.search(body)]
    return bool(pattern.search(body) and len(matches) == 1)


def _has_employer_questions(page) -> bool:
    """Stop rather than guessing answers to employer-specific questions."""
    body = (page.locator("body").inner_text(timeout=5000) or "").lower()
    markers = (
        "ответьте на вопросы работодателя",
        "вопросы работодателя",
        "ответьте на вопрос",
        "обязательный вопрос",
        "employer questions",
    )
    if any(x in body for x in markers):
        return True

    # The cover-letter textarea is expected. Other visible answer controls are not.
    visible_textareas = 0
    for i in range(page.locator("textarea").count()):
        if _visible(page.locator("textarea").nth(i)):
            visible_textareas += 1
    if visible_textareas > 1:
        return True

    controls = page.locator('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="submit"]), select')
    for i in range(controls.count()):
        if _visible(controls.nth(i)):
            return True
    return False


def apply_hh(lead: Dict, proposal: str, storage_state=None) -> Dict[str, str]:
    url = str(lead.get("url") or "")
    if not url:
        return {"status": "SKIPPED", "reason": "missing_url"}
    if not any(host in url for host in HH_HOSTS):
        return {"status": "SKIPPED", "reason": "unsupported_browser_source"}
    if not _enabled():
        return {"status": "SHORTLISTED", "reason": "browser_apply_disabled"}

    browser_state = _storage_state(storage_state)
    if not browser_state:
        return {"status": "NEEDS_HUMAN", "reason": "hh_session_missing"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("BROWSER_HEADLESS", "1") != "0")
        try:
            context = browser.new_context(storage_state=browser_state, locale="ru-RU")
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
            page.wait_for_timeout(1000)
            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            category = str(lead.get("category") or "frontend")
            if not _select_resume(page, category):
                return {"status": "NEEDS_CONFIRMATION", "reason": "matching_resume_selector_not_found"}

            if _has_employer_questions(page):
                return {"status": "NEEDS_CONFIRMATION", "reason": "employer_questions_require_human"}

            textareas = page.locator("textarea")
            visible_textarea = None
            for i in range(textareas.count()):
                if _visible(textareas.nth(i)):
                    visible_textarea = textareas.nth(i)
                    break
            if visible_textarea is None:
                return {"status": "NEEDS_CONFIRMATION", "reason": "cover_letter_field_not_found"}
            if proposal:
                visible_textarea.fill(proposal)

            submit = page.get_by_text("Отправить", exact=True)
            if submit.count() == 0:
                submit = page.get_by_text("Откликнуться", exact=True)
            if submit.count() == 0:
                return {"status": "NEEDS_CONFIRMATION", "reason": "submit_button_not_found"}

            submit.first.click(timeout=10000)
            page.wait_for_timeout(1200)
            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            body = (page.locator("body").inner_text(timeout=5000) or "").lower()
            success_markers = (
                "вы откликнулись", "отклик отправлен", "резюме доставлено", "application sent",
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

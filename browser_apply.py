"""Safe browser-based HH.ru application automation."""

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
RESUME_TITLES = {
    "frontend": "Frontend-разработчик (React)",
    "layout": "Верстальщик html/css",
    "qa": "Junior QA Engineer",
}


def _enabled():
    return os.getenv("AUTO_BROWSER_APPLY", "0") == "1"


def _looks_like_challenge(page):
    text = (page.locator("body").inner_text(timeout=5000) or "").lower()
    return any(x in text for x in (
        "captcha", "капча", "подтвердите, что вы человек", "проверка безопасности",
        "verify your identity", "security check", "two-factor", "2fa", "код подтверждения",
    ))


def _storage_state(storage_state=None):
    if storage_state:
        return storage_state
    raw = os.getenv("HH_STORAGE_STATE_JSON", "").strip()
    if raw:
        try:
            if raw.startswith("gzip-base64:"):
                compressed = base64.b64decode(raw.removeprefix("gzip-base64:"), validate=True)
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                    payload = stream.read(5 * 1024 * 1024 + 1)
                if len(payload) > 5 * 1024 * 1024:
                    raise ValueError("HH session exceeds decompressed size limit")
                return json.loads(payload)
            return json.loads(raw)
        except (ValueError, OSError, EOFError):
            return None
    return os.getenv("HH_STORAGE_STATE", "").strip() or None


def _visible(locator):
    try:
        return locator.is_visible(timeout=700)
    except Exception:
        return False


def _norm(value):
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _confirm_relocation_warning(page):
    button = page.locator('[data-qa="relocation-warning-confirm"]').first
    if _visible(button):
        button.click(timeout=5000)
        page.wait_for_timeout(500)


def _select_resume(page, category):
    """Select and verify the role-specific résumé in HH's current Magritte picker."""
    wanted = RESUME_TITLES.get(category)
    if not wanted:
        return False
    target = _norm(wanted)

    header = page.locator('[data-qa="resume-title"]').first
    if not _visible(header):
        return False

    try:
        if _norm(header.inner_text(timeout=1000)) == target:
            return True
    except Exception:
        pass

    try:
        header.click(timeout=5000)
        page.wait_for_timeout(500)
    except Exception:
        return False

    cards = page.locator('[data-magritte-select-option]')
    for _ in range(8):
        if cards.count():
            break
        page.wait_for_timeout(500)

    chosen = None
    expected = ""
    for i in range(cards.count()):
        card = cards.nth(i)
        try:
            title_node = card.locator('[data-qa="resume-title"]').first
            title = _norm(title_node.inner_text(timeout=700) if title_node.count() else card.inner_text(timeout=700))
            if title and (title == target or target in title or title in target):
                chosen = card
                expected = title
                break
        except Exception:
            continue

    # Older HH layout fallback: title cards without data-magritte-select-option.
    if chosen is None:
        titles = page.locator('[data-qa="resume-title"]')
        for i in range(titles.count()):
            node = titles.nth(i)
            try:
                title = _norm(node.inner_text(timeout=700))
                if title and (title == target or target in title or title in target):
                    chosen = node
                    expected = title
                    break
            except Exception:
                continue

    if chosen is None:
        return False

    try:
        chosen.click(timeout=5000)
        for _ in range(8):
            page.wait_for_timeout(400)
            current = page.locator('[data-qa="resume-title"]').first
            if _visible(current) and _norm(current.inner_text(timeout=700)) == expected:
                return True
    except Exception:
        return False
    return False


def _questionnaire_required(page):
    if page.locator('textarea[name^="task_"]').count():
        return True
    body = (page.locator("body").inner_text(timeout=5000) or "").lower()
    return any(x in body for x in (
        "ответьте на вопросы работодателя", "вопросы работодателя", "обязательный вопрос",
    ))


def _find_letter_area(page):
    selectors = (
        'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
        'textarea[name="letter"]',
        'textarea[name="text"]',
        'textarea[data-qa*="letter"]',
        'textarea[placeholder*="опроводитель"]',
    )
    for _ in range(10):
        for selector in selectors:
            area = page.locator(selector).first
            if _visible(area):
                return area
        toggle = page.locator('[data-qa="vacancy-response-letter-toggle"]').first
        if not _visible(toggle):
            toggle = page.get_by_text("Сопроводительное", exact=False).first
        if _visible(toggle):
            try:
                toggle.click(timeout=3000)
            except Exception:
                pass
        page.wait_for_timeout(500)
    return None


def _verify_response_sent(page, vacancy_url):
    try:
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
    except Exception:
        return False
    view = page.locator(
        '[data-qa="vacancy-response-link-view-topic"], [data-qa="vacancy-response-link-view"]'
    ).first
    if _visible(view):
        return True
    body = (page.locator("body").inner_text(timeout=5000) or "").lower()
    return any(x in body for x in (
        "вы откликнулись", "вы уже откликались", "резюме доставлено", "отклик доставлен",
    ))


def apply_hh(lead: Dict, proposal: str, storage_state=None) -> Dict[str, str]:
    raw_url = str(lead.get("url") or "")
    if not raw_url:
        return {"status": "SKIPPED", "reason": "missing_url"}
    if not any(host in raw_url for host in HH_HOSTS):
        return {"status": "SKIPPED", "reason": "unsupported_browser_source"}
    if not _enabled():
        return {"status": "SHORTLISTED", "reason": "browser_apply_disabled"}

    state = _storage_state(storage_state)
    if not state:
        return {"status": "NEEDS_HUMAN", "reason": "hh_session_missing"}

    vacancy_url = raw_url.split("?")[0]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("BROWSER_HEADLESS", "1") != "0")
        try:
            context = browser.new_context(storage_state=state, locale="ru-RU")
            page = context.new_page()
            page.goto(vacancy_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1200)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            if _verify_response_sent(page, vacancy_url):
                return {"status": "SKIPPED", "reason": "already_applied_on_hh"}

            respond = page.locator(
                '[data-qa="vacancy-response-link-top"], [data-qa="vacancy-response-link-bottom"]'
            ).first
            if not _visible(respond):
                body = (page.locator("body").inner_text(timeout=5000) or "").lower()
                if "войти" in body or "авториз" in body:
                    return {"status": "NEEDS_HUMAN", "reason": "login_required"}
                return {"status": "SKIPPED", "reason": "respond_button_not_found"}

            # Current HH opens the response modal here; nothing is counted as sent
            # until the explicit submit below and the post-submit verification pass.
            respond.click(timeout=10000)
            page.wait_for_timeout(1200)
            _confirm_relocation_warning(page)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            category = str(lead.get("category") or "frontend").lower()
            if not _select_resume(page, category):
                return {"status": "NEEDS_CONFIRMATION", "reason": "matching_resume_selector_not_found"}

            if _questionnaire_required(page):
                return {"status": "NEEDS_CONFIRMATION", "reason": "employer_questions_require_human"}

            textarea = _find_letter_area(page)
            if textarea is None:
                return {"status": "NEEDS_CONFIRMATION", "reason": "cover_letter_field_not_found"}
            textarea.fill(proposal)
            if _norm(textarea.input_value()) != _norm(proposal):
                return {"status": "FAILED", "reason": "cover_letter_not_preserved"}

            submit = None
            for selector in (
                '[data-qa="vacancy-response-submit-popup"]',
                '[data-qa="vacancy-response-letter-submit"]',
                '[data-qa="vacancy-response-submit"]',
                'button[data-qa*="response-submit"]',
                'button[type="submit"]:has-text("Откликнуться")',
                'button[type="submit"]:has-text("Отправить")',
            ):
                candidate = page.locator(selector).first
                if _visible(candidate):
                    submit = candidate
                    break
            if submit is None:
                return {"status": "NEEDS_CONFIRMATION", "reason": "submit_button_not_found"}

            submit.click(timeout=10000)
            page.wait_for_timeout(1800)
            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            if _verify_response_sent(page, vacancy_url):
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

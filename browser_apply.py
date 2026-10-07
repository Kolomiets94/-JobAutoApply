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
RESUME_NAMES = {
    "frontend": ("Frontend-разработчик (React)", "Frontend-разработчик", "React"),
    "layout": ("Верстальщик html/css", "Верстальщик HTML/CSS", "Верстальщик"),
    "qa": ("Junior QA Engineer", "QA Engineer", "Тестировщик"),
}
RESUME_PATTERNS = {
    "frontend": re.compile(r"frontend|front[ -]?end|фронт|react", re.I),
    "layout": re.compile(r"верст|вёрст|html\s*/?\s*css", re.I),
    "qa": re.compile(r"junior\s+qa|qa\s+engineer|тестиров", re.I),
}


def _enabled():
    return os.getenv("AUTO_BROWSER_APPLY", "0") == "1"


def _looks_like_challenge(page):
    text = (page.locator("body").inner_text(timeout=5000) or "").lower()
    markers = (
        "captcha", "капча", "подтвердите, что вы человек", "проверка безопасности",
        "verify your identity", "security check", "two-factor", "2fa", "код подтверждения",
    )
    return any(x in text for x in markers)


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


def _confirm_relocation_warning(page):
    button = page.locator('button[data-qa="relocation-warning-confirm"]').first
    if _visible(button):
        button.click(timeout=5000)
        page.wait_for_timeout(500)


def _select_resume(page, category):
    """Use HH's resume selector and refuse to continue if the chosen resume cannot be verified."""
    pattern = RESUME_PATTERNS.get(category)
    if not pattern:
        return False

    selector = page.locator('[data-qa*="resume-select"], [data-qa*="resume-selector"]').first
    if _visible(selector):
        selector.click(timeout=5000)
        page.wait_for_timeout(400)
        for name in RESUME_NAMES.get(category, ()):
            option = page.get_by_text(name, exact=True).first
            if _visible(option):
                option.click(timeout=5000)
                page.wait_for_timeout(400)
                return True
        # Exact labels can vary slightly; use a short visible matching option as fallback.
        options = page.locator('[role="option"], [data-qa*="resume"], button, label')
        for i in range(min(options.count(), 150)):
            node = options.nth(i)
            try:
                if not _visible(node):
                    continue
                text = (node.inner_text(timeout=500) or "").strip()
                if text and len(text) < 180 and pattern.search(text):
                    node.click(timeout=5000)
                    page.wait_for_timeout(400)
                    return True
            except Exception:
                continue
        return False

    # Some HH layouts show the already-selected resume without a chooser.
    resume_nodes = page.locator('[data-qa*="resume"]')
    visible_resume_text = []
    for i in range(min(resume_nodes.count(), 100)):
        node = resume_nodes.nth(i)
        try:
            if _visible(node):
                text = (node.inner_text(timeout=500) or "").strip()
                if text:
                    visible_resume_text.append(text)
        except Exception:
            continue
    joined = "\n".join(visible_resume_text)
    return bool(joined and pattern.search(joined))


def _questionnaire_required(page):
    # HH employer questionnaires use task_* textareas. Never invent answers.
    if page.locator('textarea[name^="task_"]').count() > 0:
        return True
    body = (page.locator("body").inner_text(timeout=5000) or "").lower()
    return any(x in body for x in (
        "ответьте на вопросы работодателя", "вопросы работодателя", "обязательный вопрос",
    ))


def apply_hh(lead: Dict, proposal: str, storage_state=None) -> Dict[str, str]:
    url = str(lead.get("url") or "")
    if not url:
        return {"status": "SKIPPED", "reason": "missing_url"}
    if not any(host in url for host in HH_HOSTS):
        return {"status": "SKIPPED", "reason": "unsupported_browser_source"}
    if not _enabled():
        return {"status": "SHORTLISTED", "reason": "browser_apply_disabled"}

    state = _storage_state(storage_state)
    if not state:
        return {"status": "NEEDS_HUMAN", "reason": "hh_session_missing"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("BROWSER_HEADLESS", "1") != "0")
        try:
            context = browser.new_context(storage_state=state, locale="ru-RU")
            page = context.new_page()
            page.goto(url.split("?")[0], wait_until="domcontentloaded", timeout=30000)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            respond = page.locator(
                'a[data-qa="vacancy-response-link-top"], button[data-qa="vacancy-response-link-top"]'
            ).first
            if not _visible(respond):
                body = (page.locator("body").inner_text(timeout=5000) or "").lower()
                if "войти" in body or "авториз" in body:
                    return {"status": "NEEDS_HUMAN", "reason": "login_required"}
                return {"status": "SKIPPED", "reason": "respond_button_not_found"}

            # Use a pre-submit flow so we can verify the correct resume before any response is sent.
            opened_form = False
            with_letter = page.get_by_text("Написать сопроводительное", exact=False).first
            if _visible(with_letter):
                with_letter.click(timeout=7000)
                opened_form = True
            else:
                dropdown = page.locator(
                    '[data-qa="vacancy-response-link-top"] + button, [data-qa="vacancy-response-link-bottom"] + button'
                ).first
                if _visible(dropdown):
                    dropdown.click(timeout=5000)
                    page.wait_for_timeout(300)
                    option = page.get_by_text("С сопроводительным письмом", exact=False).first
                    if _visible(option):
                        option.click(timeout=5000)
                        opened_form = True

            if not opened_form:
                # Clicking the plain response button can submit immediately with HH's default resume.
                # Refuse that unsafe path because this automation must use the role-matched resume.
                return {"status": "NEEDS_CONFIRMATION", "reason": "safe_pre_submit_flow_unavailable"}

            page.wait_for_timeout(700)
            _confirm_relocation_warning(page)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            category = str(lead.get("category") or "frontend").lower()
            if not _select_resume(page, category):
                return {"status": "NEEDS_CONFIRMATION", "reason": "matching_resume_selector_not_found"}

            if _questionnaire_required(page):
                return {"status": "NEEDS_CONFIRMATION", "reason": "employer_questions_require_human"}

            toggle = page.locator('[data-qa*="letter-toggle"]').first
            if not _visible(toggle):
                toggle = page.get_by_text("Написать сопроводительное", exact=False).first
            if not _visible(toggle):
                toggle = page.get_by_text("Добавить сопроводительное", exact=False).first
            if _visible(toggle):
                toggle.click(timeout=5000)
                page.wait_for_timeout(400)

            textarea = page.locator(
                'textarea[data-qa="vacancy-response-popup-form-letter-input"], textarea:not([name^="task_"])'
            ).first
            if not _visible(textarea):
                return {"status": "NEEDS_CONFIRMATION", "reason": "cover_letter_field_not_found"}
            textarea.fill(proposal)
            if textarea.input_value().strip() != proposal.strip():
                return {"status": "FAILED", "reason": "cover_letter_not_preserved"}

            submit = page.locator('button[data-qa*="vacancy-response-submit"]:visible').first
            if not _visible(submit):
                return {"status": "NEEDS_CONFIRMATION", "reason": "submit_button_not_found"}

            submit.click(timeout=10000)
            page.wait_for_timeout(1000)

            if _looks_like_challenge(page):
                return {"status": "NEEDS_HUMAN", "reason": "security_challenge"}

            success = page.locator(
                '[data-qa="vacancy-response-success"], [data-qa="vacancy-response-link-view-topic"]'
            ).first
            if _visible(success):
                return {"status": "SUBMITTED", "reason": "browser_hh_sent"}

            body = (page.locator("body").inner_text(timeout=5000) or "").lower()
            if any(x in body for x in ("вы откликнулись", "отклик отправлен", "резюме доставлено")):
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

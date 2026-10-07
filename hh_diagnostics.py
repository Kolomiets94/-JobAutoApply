"""Read-only HH session and API diagnostics; never submits applications."""
import json
import requests
from playwright.sync_api import sync_playwright
from browser_apply import _storage_state, _looks_like_challenge


def diagnose():
    result = {"api": "not_checked", "session": "not_checked"}
    try:
        response = requests.get(
            "https://api.hh.ru/vacancies",
            params={"text": "Junior Frontend React", "per_page": 1},
            headers={"User-Agent": "JobFreelanceHunter/1.1"},
            timeout=20,
        )
        result["api_http_status"] = response.status_code
        result["api"] = "ok" if response.ok else "request_failed"
    except requests.RequestException as exc:
        result["api"] = type(exc).__name__

    state = _storage_state()
    if not isinstance(state, dict) or not state.get("cookies"):
        result["session"] = "missing_or_invalid"
        return result
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=state, locale="ru-RU")
            page = context.new_page()
            page.goto("https://hh.ru/applicant/profile/me", wait_until="domcontentloaded", timeout=45000)
            if _looks_like_challenge(page):
                result["session"] = "security_challenge"
            elif "/account/login" in page.url or "/login" in page.url:
                result["session"] = "login_required"
            else:
                body = page.locator("body").inner_text(timeout=5000).lower()
                markers = page.locator('[data-qa="mainmenu_myResumes"], [data-qa="mainmenu_applicantProfile"]').count()
                if markers or "мои резюме" in body:
                    result["session"] = "authenticated"
                elif page.locator('input[type="password"], input[type="tel"]').count():
                    result["session"] = "login_required"
                else:
                    result["session"] = "unconfirmed"
        except Exception as exc:
            result["session"] = type(exc).__name__
        finally:
            browser.close()
    if result["session"] == "authenticated":
        try:
            from hh_web_search import search_hh_web
            leads = search_hh_web("frontend", "Junior Frontend React")
            result["web_search"] = "ok"
            result["web_search_count"] = len(leads)
            result["web_search_titles"] = [lead["title"] for lead in leads[:5]]
        except Exception as exc:
            result["web_search"] = type(exc).__name__
    return result



def inspect_response_form():
    state = _storage_state()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=state, locale="ru-RU")
            page = context.new_page()
            page.goto("https://hh.ru/vacancy/137786463", wait_until="domcontentloaded", timeout=45000)
            if _looks_like_challenge(page):
                return {"status": "security_challenge"}
            respond = page.get_by_text("Откликнуться", exact=True)
            if not respond.count():
                return {"status": "respond_button_not_found"}
            respond.first.click(timeout=10000)
            page.wait_for_timeout(1500)
            if _looks_like_challenge(page):
                return {"status": "security_challenge"}
            return {
                "status": "form_opened",
                "controls": page.evaluate("""() => Array.from(document.querySelectorAll('input,select,textarea,button,[role="radio"],[role="combobox"]')).map(e=>({tag:e.tagName,type:e.type||'',role:e.getAttribute('role')||'',qa:e.getAttribute('data-qa')||'',name:e.getAttribute('name')||'',label:e.getAttribute('aria-label')||'',text:(e.innerText||'').slice(0,120)})).slice(-60)"""),
                "labels": page.locator("label").all_text_contents(),
                "form_text": page.locator('form').all_text_contents(),
            }
        finally:
            browser.close()


if __name__ == "__main__":
    result = diagnose()
    result["response_form"] = inspect_response_form()
    print(json.dumps(result, ensure_ascii=False))

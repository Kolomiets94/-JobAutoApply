"""Rank leads by expected profitability and resume fit."""
import re
from typing import Any, Dict

SKILLS = {
    "react": 1.0, "typescript": 1.0, "javascript": .8, "js": .45, "html": .7,
    "css": .7, "scss": .7, "figma": .5, "redux": .7, "redux toolkit": .8,
    "rest api": .6, "vite": .55, "webpack": .55, "git": .4,
    "frontend": .65, "front-end": .65, "верстка": .7, "вёрстка": .7,
    "верстка сайта": .85, "вёрстка сайта": .85, "верстальщик": .85,
    "лендинг": .55, "landing": .55, "адаптив": .5, "сайт": .25,
    "qa": .55, "tester": .55, "тестировщик": .55, "manual qa": .65,
}
BLOCK = (
    "middle", "mid-level", "mid level", "senior", "lead ", "team lead", "tech lead", "head of", "manager", "director", "fullstack", "full stack",
    "node.js required", "internship", "trainee", "стажировка", "стажер", "стажёр",
    "ai engineer", "ai agent engineer", "machine learning engineer", "ml engineer", "security engineer", "security analyst", "cybersecurity",
    "coreldraw", "полиграф", "типограф", "для печати", "визитк",
    "логотип", "illustrator", "интерьер", "3d-модел",
)
RUSSIA_SOURCES = {"hh", "fl_ru", "habr_freelance", "freelancehunt"}
INTERNATIONAL_SOURCES = {"remoteok", "peopleperhour", "prolinker", "prolinker_firecrawl", "upwork_frontend"}
FREELANCE_SOURCES = {"fl_ru", "habr_freelance", "freelancehunt", "peopleperhour", "prolinker", "prolinker_firecrawl", "upwork_frontend"}
FREELANCE_TOO_COMPLEX = (
    "architect", "архитектор", "devops", "kubernetes", "terraform", "microservices",
    "микросервис", "highload", "high-load", "machine learning", "data engineer",
    "blockchain", "web3", "smart contract", "1c", "bitrix", "битрикс",
    "django", "laravel", "spring boot", ".net", "golang", "rust",
)


def _text(lead: Dict[str, Any]) -> str:
    return " ".join(
        str(lead.get(k) or "")
        for k in ("title", "description", "requirements", "category", "location", "region")
    ).lower()


def _money(lead: Dict[str, Any]) -> float:
    s = lead.get("budget") or lead.get("salary") or ""
    if isinstance(s, dict):
        vals = [x for x in (s.get("from"), s.get("to"), s.get("amount")) if isinstance(x, (int, float))]
        return float(max(vals)) if vals else 0.0
    nums = [
        float(x.replace(" ", "").replace(",", "."))
        for x in re.findall(r"\d[\d ]*(?:[.,]\d+)?", str(s))
    ]
    return max(nums, default=0.0)


def _explicit_salary_rejected(lead: Dict[str, Any]) -> bool:
    salary = lead.get("salary")
    if not salary:
        return False
    source = str(lead.get("source") or "").lower()
    if isinstance(salary, dict):
        currency = str(salary.get("currency") or "").upper()
        vals = [x for x in (salary.get("from"), salary.get("to"), salary.get("amount")) if isinstance(x, (int, float))]
        amount = max(vals) if vals else None
        if amount is None:
            return False
        if currency in ("RUR", "RUB") or source in RUSSIA_SOURCES:
            return amount < 60000
        if currency in ("USD", "$"):
            # RemoteOK-style annual salaries are converted to a monthly comparison.
            monthly = amount / 12.0 if amount > 12000 else amount
            return monthly < 2000
    return False


def _location_rejected(lead: Dict[str, Any], text: str) -> bool:
    # Explicit worldwide/anywhere is always acceptable unless the listing itself says otherwise.
    if any(x in text for x in ("remote worldwide", "worldwide", "work from anywhere", "anywhere in the world")):
        return False
    restricted = (
        "must reside in", "must be located in", "must live in", "residents only",
        "us only", "u.s. only", "uk only", "eu only", "europe only",
        "right to work in", "work authorization", "work authorisation",
        "visa sponsorship is not available", "no visa sponsorship",
    )
    return any(x in text for x in restricted)


def rank_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    text = _text(lead)
    if any(x in text for x in BLOCK):
        return {**lead, "profit_score": 0, "eligible": False, "rank_reason": "excluded requirement"}
    if _explicit_salary_rejected(lead):
        return {**lead, "profit_score": 0, "eligible": False, "rank_reason": "salary below configured floor"}
    if _location_rejected(lead, text):
        return {**lead, "profit_score": 0, "eligible": False, "rank_reason": "explicit location/work-authorization restriction"}

    source = str(lead.get("source") or "").lower()
    if source in FREELANCE_SOURCES and any(x in text for x in FREELANCE_TOO_COMPLEX):
        return {**lead, "profit_score": 0, "eligible": False, "rank_reason": "freelance project too complex/out of scope"}

    matched = [k for k in SKILLS if k in text]
    fit = sum(SKILLS[k] for k in matched) / max(sum(SKILLS.values()), 1)
    budget = _money(lead)
    budget_score = min(budget / 30000.0, 1.0) if budget else .25
    quick = .15 if any(x in text for x in ("лендинг", "landing", "верст", "fix", "bug", "правк")) else 0
    competition = lead.get("proposals")
    comp_score = .15 if isinstance(competition, int) and competition < 10 else 0
    resume_match = lead.get("match_score")
    resume_score = (resume_match / 100.0) if isinstance(resume_match, (int, float)) else 0

    score = round(min(100, (fit * .45 + budget_score * .25 + quick + comp_score + resume_score * .25) * 100))
    return {
        **lead,
        "profit_score": score,
        # One relevant skill is enough to enter the shortlist; safety filters above still apply.
        "eligible": bool(matched) and score >= 8,
        "matched_skills": matched,
        "rank_reason": "skill fit + budget + speed + competition + resume fit",
    }


def rank_leads(leads):
    ranked = [rank_lead(x) for x in leads]
    return sorted((x for x in ranked if x["eligible"]), key=lambda x: x["profit_score"], reverse=True)

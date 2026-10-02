"""Rank freelance leads by expected profitability.

No credentials or personal data are stored here.  The score is deliberately
transparent so it can be tuned without an AI/API dependency.
"""
import re
from typing import Any, Dict

SKILLS = {
    "react": 1.0, "typescript": 1.0, "javascript": .8, "js": .45, "html": .7,
    "css": .7, "scss": .7, "figma": .5, "redux": .7, "rest api": .6,
    "frontend": .65, "front-end": .65, "верст": .7, "вёрст": .7,
    "лендинг": .55, "landing": .55, "адаптив": .5, "сайт": .25,
}
BLOCK = ("senior", "lead ", "fullstack", "full stack", "node.js required",
         "internship", "trainee", "стажировка", "стажер", "стажёр")

def _text(lead: Dict[str, Any]) -> str:
    return " ".join(str(lead.get(k) or "") for k in
                    ("title","description","requirements","category")).lower()

def _money(lead: Dict[str, Any]) -> float:
    s = lead.get("budget") or lead.get("salary") or ""
    if isinstance(s, dict):
        vals=[x for x in (s.get("from"),s.get("to")) if isinstance(x,(int,float))]
        return float(max(vals)) if vals else 0.0
    nums=[float(x.replace(" ","").replace(",", ".")) for x in
          re.findall(r"\d[\d ]*(?:[.,]\d+)?", str(s))]
    return max(nums, default=0.0)

def rank_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    text=_text(lead)
    if any(x in text for x in BLOCK):
        return {**lead, "profit_score": 0, "eligible": False,
                "rank_reason": "excluded requirement"}
    matched=[k for k in SKILLS if k in text]
    fit=sum(SKILLS[k] for k in matched)/max(sum(SKILLS.values()),1)
    budget=_money(lead)
    budget_score=min(budget/30000.0, 1.0) if budget else .25
    quick=.15 if any(x in text for x in ("лендинг","landing","верст","fix","bug","правк")) else 0
    competition=lead.get("proposals")
    comp_score=.15 if isinstance(competition,int) and competition < 10 else 0
    score=round(min(100, (fit*.55+budget_score*.30+quick+comp_score)*100))
    return {**lead, "profit_score": score, "eligible": bool(matched) and score >= 12,
            "matched_skills": matched,
            "rank_reason": "skill fit + budget + speed + competition"}

def rank_leads(leads):
    ranked=[rank_lead(x) for x in leads]
    return sorted((x for x in ranked if x["eligible"]),
                  key=lambda x:x["profit_score"], reverse=True)

"""Freelancehunt API adapter. Token stays in environment, never in git."""
import os, requests

BASE="https://api.freelancehunt.com/v2"

def _headers():
    token=os.getenv("FREELANCEHUNT_TOKEN")
    if not token: return None
    return {"Authorization":f"Bearer {token}","Accept-Language":"ru"}

def collect_freelancehunt():
    h=_headers()
    if not h: return []
    r=requests.get(f"{BASE}/projects",headers=h,params={"filter[only_my_skills]":1},timeout=20)
    r.raise_for_status()
    out=[]
    for row in r.json().get("data",[]):
        a=row.get("attributes") or {}
        budget=a.get("budget") or {}
        out.append({"source":"freelancehunt","category":"freelance",
          "external_id":str(row.get("id")),"title":a.get("name"),
          "description":a.get("description_html") or a.get("description") or "",
          "budget":budget,"published":a.get("published_at"),
          "url":f"https://freelancehunt.com/project/{row.get('id')}.html",
          "can_api_bid":True})
    return out

def add_bid(lead,proposal,days=3):
    h=_headers()
    if not h: return {"status":"SHORTLISTED","reason":"freelancehunt_token_missing"}
    budget=lead.get("budget") or {}
    amount=budget.get("amount")
    currency=budget.get("currency")
    if not amount or currency not in ("UAH","RUB"):
        return {"status":"NEEDS_CONFIRMATION","reason":"budget_missing"}
    body={"days":days,"safe_type":"employer",
          "budget":{"amount":amount,"currency":currency},
          "comment":proposal,"is_hidden":False}
    r=requests.post(f"{BASE}/projects/{lead['external_id']}/bids",
                    headers={**h,"Content-Type":"application/json"},json=body,timeout=20)
    if r.status_code in (200,201):
        return {"status":"SUBMITTED","reason":"freelancehunt_api_bid"}
    return {"status":"FAILED","reason":f"freelancehunt_http_{r.status_code}"}

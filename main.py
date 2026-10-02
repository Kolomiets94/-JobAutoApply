import re, json, hashlib
from datetime import datetime, timezone
import requests
from freelance_sources import collect_freelance
HH_API="https://api.hh.ru/vacancies"
QUERIES=[("frontend","React TypeScript junior"),("layout","верстальщик HTML CSS"),("qa","junior QA tester"),("freelance_frontend","React TypeScript проект"),("freelance_bot","Telegram bot Python")]
EXCLUDE=("стажер","стажировка","internship","trainee","full stack","fullstack")
UA={"User-Agent":"JobFreelanceHunter/1.1"}
def ok(v):
    text=((v.get("name") or "")+" "+" ".join(str(x or "") for x in (v.get("snippet") or {}).values())).lower()
    if any(x in text for x in EXCLUDE): return False
    return (v.get("schedule") or {}).get("id")=="remote" or "удален" in text or "remote" in text
def hh_search(tag,q):
    r=requests.get(HH_API,params={"text":q,"per_page":50,"order_by":"publication_time"},headers=UA,timeout=20); r.raise_for_status()
    return [{"source":"hh","category":tag,"title":v["name"],"company":(v.get("employer") or {}).get("name"),"url":v.get("alternate_url"),"published":v.get("published_at"),"salary":v.get("salary")} for v in r.json().get("items",[]) if ok(v)]
def remoteok():
    try:
        data=requests.get("https://remoteok.com/api",headers=UA,timeout=20).json(); out=[]
        for v in data[1:]:
            text=((v.get("position") or "")+" "+(v.get("description") or "")).lower()
            if ("react" in text or "typescript" in text) and not any(x in text for x in EXCLUDE):
                out.append({"source":"remoteok","category":"frontend","title":v.get("position"),"company":v.get("company"),"url":v.get("url"),"published":v.get("date")})
        return out[:50]
    except Exception:return []
def collect():
    jobs=[]
    for tag,q in QUERIES:
        try:jobs+=hh_search(tag,q)
        except Exception:pass
    jobs+=remoteok()
    try: jobs+=collect_freelance()
    except Exception: pass
    seen=set(); unique=[]
    for j in jobs:
        k=hashlib.sha256((j.get("url") or json.dumps(j,sort_keys=True)).encode()).hexdigest()
        if k not in seen:seen.add(k);unique.append(j)
    unique.sort(key=lambda x:x.get("published") or "",reverse=True)
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(unique),"items":unique[:100]}
if __name__=="__main__":print(json.dumps(collect(),ensure_ascii=False,indent=2))

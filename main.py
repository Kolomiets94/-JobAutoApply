import os, re, json, hashlib
from datetime import datetime, timezone
import requests

HH_API="https://api.hh.ru/vacancies"
QUERIES=[
 ("frontend","React TypeScript junior"),
 ("layout","верстальщик HTML CSS"),
 ("qa","junior QA tester"),
 ("freelance_frontend","React TypeScript проект"),
 ("freelance_bot","Telegram bot Python"),
]
EXCLUDE=("стажер","стажировка","internship","trainee","full stack","fullstack")
UA={"User-Agent":"JobFreelanceHunter/1.0 (candidate job search)"}

def ok(v):
    name=(v.get("name") or "").lower()
    snippet=" ".join((v.get("snippet") or {}).values()).lower()
    text=name+" "+re.sub("<[^>]+>"," ",snippet)
    if any(x in text for x in EXCLUDE): return False
    sched=(v.get("schedule") or {}).get("id")
    return sched=="remote" or "удален" in text or "remote" in text

def hh_search(tag,q):
    p={"text":q,"per_page":50,"order_by":"publication_time","search_field":"name"}
    r=requests.get(HH_API,params=p,headers=UA,timeout=25); r.raise_for_status()
    out=[]
    for v in r.json().get("items",[]):
        if ok(v):
            out.append({"source":"hh","category":tag,"title":v["name"],
             "company":(v.get("employer") or {}).get("name"),"url":v.get("alternate_url"),
             "published":v.get("published_at"),"salary":v.get("salary")})
    return out

def remoteok():
    try:
        data=requests.get("https://remoteok.com/api",headers=UA,timeout=25).json()
        out=[]
        for v in data[1:]:
            text=((v.get("position") or "")+" "+(v.get("description") or "")).lower()
            if ("react" in text or "typescript" in text) and not any(x in text for x in EXCLUDE):
                out.append({"source":"remoteok","category":"frontend","title":v.get("position"),
                 "company":v.get("company"),"url":v.get("url"),"published":v.get("date")})
        return out[:50]
    except Exception:
        return []

def main():
    jobs=[]
    for tag,q in QUERIES:
        try: jobs += hh_search(tag,q)
        except Exception as e: print("HH",tag,e)
    jobs += remoteok()
    seen=set(); unique=[]
    for j in jobs:
        k=hashlib.sha256((j.get("url") or json.dumps(j,sort_keys=True)).encode()).hexdigest()
        if k not in seen: seen.add(k); unique.append(j)
    unique.sort(key=lambda x:x.get("published") or "",reverse=True)
    result={"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(unique),"items":unique[:100]}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()

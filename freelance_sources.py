"""Public freelance feeds.

Uses public RSS feeds only: no login, CAPTCHA handling, or private endpoints.
Failures are isolated so one source never stops the hunter.
"""
import html, re
from xml.etree import ElementTree as ET
import requests

UA={"User-Agent":"JobFreelanceHunter/2.0"}
FEEDS=(
    ("habr_freelance","https://freelance.habr.com/rss/tasks"),
    ("fl_ru","https://www.fl.ru/rss/all.xml"),
)

def _clean(s):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s or ""))).strip()

def _entries(xml, source):
    root=ET.fromstring(xml)
    out=[]
    for item in root.findall(".//item"):
        title=_clean(item.findtext("title"))
        desc=_clean(item.findtext("description"))
        link=(item.findtext("link") or "").strip()
        pub=(item.findtext("pubDate") or "").strip()
        if link and title:
            out.append({"source":source,"category":"freelance","title":title,
                        "description":desc[:5000],"url":link,"published":pub})
    return out

def collect_freelance():
    leads=[]
    for source,url in FEEDS:
        try:
            r=requests.get(url,headers=UA,timeout=20)
            r.raise_for_status()
            leads.extend(_entries(r.text,source))
        except Exception:
            continue
    return leads

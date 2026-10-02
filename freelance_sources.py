"""Public freelance feeds.

Uses public feeds/listings only: no login, CAPTCHA handling, or private endpoints.
Failures are isolated so one source never stops the hunter.
"""
import html, re
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
import requests

UA={"User-Agent":"Mozilla/5.0 (compatible; JobFreelanceHunter/2.1; +https://github.com/Kolomiets94/-JobAutoApply)"}
FEEDS=(
    ("habr_freelance","https://freelance.habr.com/rss/tasks"),
    ("fl_ru","https://www.fl.ru/rss/all.xml"),
    ("upwork_frontend","https://www.upwork.com/ab/feed/jobs/rss?q=React%20OR%20TypeScript%20OR%20HTML%20OR%20CSS&sort=recency"),
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
            lead={"source":source,"category":"freelance","title":title,
                  "description":desc[:5000],"url":link,"published":pub}
            # FL.ru responses can require paid platform actions; never auto-submit them.
            if source=="fl_ru":
                lead["paid_bid"]=True
            out.append(lead)
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

def collect_prolinker(max_pages=10):
    """Collect public ProLinker frontend listings across normal GET pagination."""
    base="https://prolinker.com"
    out=[]
    seen=set()
    for page in range(1,max_pages+1):
        url=f"{base}/projects/s/frontend?skills=Frontend&page={page}"
        try:
            r=requests.get(url,headers=UA,timeout=25)
            r.raise_for_status()
        except Exception:
            continue

        # Project detail URLs are nested paths under /projects/, while listing/filter
        # routes (/projects/s/...) must be excluded.
        hrefs=re.findall(r'href=["\']([^"\']*?/projects/[^"\'#?]+)["\']',r.text,re.I)
        for href in hrefs:
            absolute=urljoin(base,html.unescape(href))
            path=absolute.split("prolinker.com",1)[-1]
            if path.startswith("/projects/s/") or absolute in seen:
                continue

            # Slug is the most reliable title available without depending on CSS classes.
            slug=path.rstrip("/").rsplit("/",1)[-1]
            if not slug or slug in {"projects","frontend"}:
                continue
            title=re.sub(r"-[A-Z0-9]{5,}$","",slug,flags=re.I)
            title=_clean(title.replace("-"," "))
            if not title:
                continue

            seen.add(absolute)
            out.append({
                "source":"prolinker",
                "category":"freelance",
                "title":title,
                "description":title,
                "url":absolute,
                "published":"",
            })
    return out

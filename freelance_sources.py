"""Public freelance feeds and listings.

Uses public feeds/listings only: no login, CAPTCHA handling, or private endpoints.
Failures are isolated so one source never stops the hunter.
"""
import html, re
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
import requests

UA={"User-Agent":"Mozilla/5.0 (compatible; JobFreelanceHunter/2.2; +https://github.com/Kolomiets94/-JobAutoApply)"}
FEEDS=(
    ("habr_freelance","https://freelance.habr.com/rss/tasks"),
    ("fl_ru","https://www.fl.ru/rss/all.xml"),
    ("upwork_frontend","https://www.upwork.com/ab/feed/jobs/rss?q=React%20OR%20TypeScript%20OR%20HTML%20OR%20CSS&sort=recency"),
)
FIRECRAWL_SCRAPE="https://api.firecrawl.dev/v2/scrape"

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

def _firecrawl_markdown(url):
    """Firecrawl Keyless scrape: no account/API key required for the free allowance."""
    r=requests.post(
        FIRECRAWL_SCRAPE,
        headers={"Content-Type":"application/json","User-Agent":UA["User-Agent"]},
        json={"url":url,"formats":["markdown"],"onlyMainContent":True},
        timeout=45,
    )
    r.raise_for_status()
    data=r.json()
    if not data.get("success"):
        return ""
    return (data.get("data") or {}).get("markdown","") or data.get("markdown","") or ""

def _parse_prolinker_markdown(md):
    out=[]
    seen=set()
    # Firecrawl markdown preserves project anchors as [title](absolute-url).
    pattern=r'\[([^\]]+)\]\((https://prolinker\.com/projects/(?!s/)[^)]+)\)'
    for label,href in re.findall(pattern,md,re.I):
        title=_clean(label)
        href=html.unescape(href.strip())
        if not title or href in seen:
            continue
        seen.add(href)
        # Keep nearby listing text so the ranker can see budget/location/technology hints.
        pos=md.find(f"]({href})")
        context=_clean(md[pos:pos+700]) if pos >= 0 else title
        out.append({
            "source":"prolinker_firecrawl",
            "category":"freelance",
            "title":title,
            "description":context[:1500],
            "url":href,
            "published":"",
        })
    return out

def collect_prolinker(max_pages=10):
    """Collect ProLinker via Firecrawl Keyless, with direct HTML as fallback."""
    base="https://prolinker.com"
    out=[]
    seen=set()
    for page in range(1,max_pages+1):
        url=f"{base}/projects/s/frontend?skills=Frontend&page={page}"
        page_leads=[]
        try:
            page_leads=_parse_prolinker_markdown(_firecrawl_markdown(url))
        except Exception:
            pass

        # Cheap fallback if ProLinker happens to allow direct server access.
        if not page_leads:
            try:
                r=requests.get(url,headers=UA,timeout=25)
                r.raise_for_status()
                hrefs=re.findall(r'href=["\']([^"\']*?/projects/[^"\'#?]+)["\']',r.text,re.I)
                for href in hrefs:
                    absolute=urljoin(base,html.unescape(href))
                    path=absolute.split("prolinker.com",1)[-1]
                    if path.startswith("/projects/s/"):
                        continue
                    slug=path.rstrip("/").rsplit("/",1)[-1]
                    title=_clean(re.sub(r"-[A-Z0-9]{5,}$","",slug,flags=re.I).replace("-"," "))
                    if title:
                        page_leads.append({"source":"prolinker","category":"freelance","title":title,
                                           "description":title,"url":absolute,"published":""})
            except Exception:
                pass

        for lead in page_leads:
            if lead["url"] not in seen:
                seen.add(lead["url"])
                out.append(lead)
    return out

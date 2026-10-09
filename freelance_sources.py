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
PPH_URLS=(
    "https://www.peopleperhour.com/freelance-react-js-jobs?sort=latest",
    "https://www.peopleperhour.com/freelance-front-end-developer-jobs?sort=latest",
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
            if source=="fl_ru":
                # FL.ru has free-to-apply vacancies and "for everyone" orders.
                # RSS does not expose that flag: never label every listing paid.
                lead["bid_access_unknown"]=True
            out.append(lead)
    return out

def collect_freelance():
    leads=[]
    for source,url in FEEDS:
        try:
            r=requests.get(url,headers=UA,timeout=20)
            r.raise_for_status()
            leads.extend(_entries(r.text,source))
        except Exception as exc:
            print(f"[freelance-feed] {source} failed: {type(exc).__name__}: {exc}", flush=True)
            continue
    print(f"[freelance-feed] total: {len(leads)} leads", flush=True)
    return leads

def _firecrawl_markdown(url):
    """Firecrawl Keyless scrape: no account/API key required for the free allowance."""
    r=requests.post(
        FIRECRAWL_SCRAPE,
        headers={"Content-Type":"application/json","User-Agent":UA["User-Agent"]},
        json={"url":url,"formats":["markdown"],"onlyMainContent":True},
        timeout=45,
    )
    if not r.ok:
        print(f"[firecrawl] HTTP {r.status_code}: {r.text[:500]}", flush=True)
        r.raise_for_status()
    data=r.json()
    if not data.get("success"):
        print(f"[firecrawl] unsuccessful: {str(data)[:500]}", flush=True)
        return ""
    return (data.get("data") or {}).get("markdown","") or data.get("markdown","") or ""

def _parse_prolinker_markdown(md):
    out=[]
    seen=set()
    # Firecrawl markdown preserves project anchors as [title](absolute-url).
    pattern=r'\[([^\]]+)\]\((https://prolinker\.com/projects/(?!s/)[^)]+)\)'
    matches = list(re.finditer(pattern, md, re.I))
    for index, match in enumerate(matches):
        label, href = match.groups()
        title=_clean(label)
        href=html.unescape(href.strip())
        if not title or href in seen:
            continue
        seen.add(href)
        # Keep nearby listing text so the ranker can see budget/location/technology hints.
        # Never borrow skills from the next listing on a search-results page.
        end = matches[index + 1].start() if index + 1 < len(matches) else len(md)
        context = _clean(md[match.end():min(end, match.end() + 700)])
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
        except Exception as exc:
            print(f"[prolinker] Firecrawl page {page} failed: {type(exc).__name__}: {exc}", flush=True)

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
            except Exception as exc:
                print(f"[prolinker] direct page {page} failed: {type(exc).__name__}: {exc}", flush=True)

        print(f"[prolinker] page {page}: {len(page_leads)} leads", flush=True)
        for lead in page_leads:
            if lead["url"] not in seen:
                seen.add(lead["url"])
                out.append(lead)
    return out


def collect_peopleperhour():
    """Collect public PeoplePerHour frontend project cards. Discovery only; no auto-bidding."""
    out=[]
    seen=set()
    for url in PPH_URLS:
        try:
            r=requests.get(url,headers=UA,timeout=25)
            r.raise_for_status()
            # Public project links use /freelance-jobs/... paths; keep only unique project URLs.
            links=re.findall(r'href=["\'](https?://www\.peopleperhour\.com/freelance-jobs/[^"\'#?]+|/freelance-jobs/[^"\'#?]+)["\']',r.text,re.I)
            for href in links:
                absolute=urljoin("https://www.peopleperhour.com",html.unescape(href))
                if absolute in seen:
                    continue
                seen.add(absolute)
                slug=absolute.rstrip("/").rsplit("/",1)[-1]
                title=_clean(slug.replace("-"," "))
                if title:
                    out.append({"source":"peopleperhour","category":"freelance","title":title,
                                "description":title,"url":absolute,"published":"",
                                "apply_email":None})
        except Exception as exc:
            print(f"[peopleperhour] failed: {type(exc).__name__}: {exc}",flush=True)
    print(f"[peopleperhour] {len(out)} leads",flush=True)
    return out

"""Public job sources. Discovery and delivery capabilities stay separate."""
import html
import re
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
import requests

UA = {'User-Agent': 'Mozilla/5.0 (compatible; JobFreelanceHunter/3.0)'}


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))).strip()


def response(url, **params):
    r = requests.get(url, params=params or None, headers=UA, timeout=20)
    r.raise_for_status()
    return r


def job(source, title, url, description='', **extra):
    return {'source': source, 'title': clean(title), 'url': url,
            'description': clean(description), 'remote': True, **extra}


def jobicy():
    data = response('https://jobicy.com/api/v2/remote-jobs', count=100).json()
    return [job('jobicy', v.get('jobTitle'), v.get('url'), v.get('jobDescription'),
                company=v.get('companyName'), location=v.get('jobGeo'),
                published=v.get('pubDate'), language='en',
                salary={'from': v.get('salaryMin'), 'to': v.get('salaryMax'),
                        'currency': v.get('salaryCurrency'), 'period': v.get('salaryPeriod')})
            for v in data.get('jobs', []) if v.get('url')]


def remotive():
    data = response('https://remotive.com/api/remote-jobs').json()
    return [job('remotive', v.get('title'), v.get('url'), v.get('description'),
                company=v.get('company_name'), location=v.get('candidate_required_location'),
                published=v.get('publication_date'), language='en')
            for v in data.get('jobs', []) if v.get('url')]


def arbeitnow():
    data = response('https://www.arbeitnow.com/api/job-board-api').json()
    return [job('arbeitnow', v.get('title'), v.get('url'), v.get('description'),
                company=v.get('company_name'), location=v.get('location'), language='en')
            for v in data.get('data', []) if v.get('remote') and v.get('url')]


def feed(source, url, language):
    root = ET.fromstring(response(url).content)
    out = []
    for item in root.findall('.//item'):
        link = item.findtext('link') or ''
        desc = item.findtext('description') or ''
        # Habr RSS includes onsite positions; keep only explicitly remote ones.
        text = clean(desc).lower()
        if source == 'habr_career' and not any(s in text for s in ('удалён', 'удален', 'remote')):
            continue
        if link:
            out.append(job(source, item.findtext('title'), link, desc,
                           published=item.findtext('pubDate'), language=language))
    return out


def habr_career():
    return feed('habr_career', 'https://career.habr.com/vacancies/rss', 'ru')


def weworkremotely():
    return feed('weworkremotely', 'https://weworkremotely.com/remote-jobs.rss', 'en')


def trudvsem():
    out = []
    for query in ('junior frontend', 'верстальщик', 'junior тестировщик'):
        data = response('https://opendata.trudvsem.ru/api/v1/vacancies', text=query, limit=100, offset=0).json()
        for wrapper in (data.get('results') or {}).get('vacancies', []):
            v = wrapper.get('vacancy', wrapper)
            desc = ' '.join(str(v.get(k) or '') for k in ('duty', 'requirements', 'requirement', 'schedule', 'employment'))
            if not any(s in clean(desc).lower() for s in ('удалён', 'удален', 'дистанцион', 'remote')):
                continue
            url = v.get('vac_url')
            if not url:
                continue
            out.append(job('trudvsem', v.get('job-name'), url, desc,
                           company=(v.get('company') or {}).get('name'), language='ru',
                           apply_email=next((c.get('contact_value') for c in v.get('contact_list', [])
                                             if c.get('contact_type') == 'Эл. почта'), None),
                           salary={'from': v.get('salary_min'), 'to': v.get('salary_max'), 'currency': 'RUB'}))
    return out


JOB_COLLECTORS = (('habr_career', habr_career), ('trudvsem', trudvsem),
                  ('jobicy', jobicy), ('remotive', remotive),
                  ('weworkremotely', weworkremotely), ('arbeitnow', arbeitnow))

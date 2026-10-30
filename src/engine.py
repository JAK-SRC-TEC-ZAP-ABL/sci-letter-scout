"""Metadata collection, normalization and conservative paper prioritization.

The rapid path covers all configured titles through PubMed (only after PubMed
indexing). Crossref is rotated in small batches to avoid hammering the API.
Neither represents guaranteed near-real-time publisher-side discovery.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_AGENT = "SCILetterScout/0.1 (public research metadata monitoring; contact via repository)"


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def http_get_json(url, params, retries=2):
    qs = urllib.parse.urlencode(params, doseq=True)
    return json.loads(_request(url + '?' + qs, retries=retries).decode('utf-8'))


def _request(url, payload=None, retries=2):
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    email = os.environ.get('CONTACT_EMAIL')
    if email:
        headers['User-Agent'] = f'{USER_AGENT} ({email})'
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=payload, headers=headers), timeout=25) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == retries or (isinstance(e, urllib.error.HTTPError) and e.code in {400, 401, 403, 404}):
                raise
            time.sleep(min(2 ** attempt + 1, 7))


def normalize_title(s):
    return re.sub(r'[^a-z0-9]+', '', str(s or '').casefold())


def clean_text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', str(s or '')))).strip()


def doi_key(doi):
    d = urllib.parse.unquote(str(doi or '').strip().lower())
    d = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:)', '', d)
    return d.rstrip('.,;')


def unique_id(paper):
    doi = doi_key(paper.get('doi'))
    if doi:
        return 'doi:' + doi
    if paper.get('pmid'):
        return 'pmid:' + str(paper['pmid'])
    return None


def iso_date_from_parts(parts):
    if not parts or not parts[0]:
        return None
    try:
        year, month, day = (int(x) for x in (list(parts) + [1, 1])[:3])
        return dt.date(year, month, day).isoformat()
    except (ValueError, TypeError):
        return None


def crossref_publication_date(m):
    for field in ('published-online', 'published', 'issued'):
        parts = m.get(field, {}).get('date-parts', [])
        if parts:
            return iso_date_from_parts(parts[0])
    return None


def classify_type(text):
    t = (text or '').lower()
    rules = {
        'mendelian_randomization': ['mendelian randomization', 'mendelian randomisation'],
        'single_cell': ['single-cell', 'single cell', 'scrna-seq', 'spatial transcriptomic'],
        'machine_learning': ['machine learning', 'deep learning', 'random forest', 'predictive model'],
        'clinical_trial': ['randomized', 'randomised', 'phase iii', 'phase 3', 'clinical trial'],
        'meta_analysis': ['meta-analysis', 'systematic review'],
        'mechanism': ['mechanism', 'knockout', 'crispr', 'tumor microenvironment', 'immunotherapy'],
    }
    return [k for k, words in rules.items() if any(w in t for w in words)] or ['other']


_ONCOLOGY_TERMS = re.compile(
    r'\b(?:cancer|tumou?r|neoplasm|oncolog|carcinom|adenocarcinom|'
    r'leuk[ae]mi|lymphom|melanom|sarcom|glioblastom|gliom|'
    r'myelo[mad]|metast[a-z]*|malignan|chemotherap|radiotherap|'
    r'immunotherap|antineoplastic|hepatocellular carcinoma)[a-z]*\b',
    re.IGNORECASE,
)


def relevant_to_catalog(paper):
    """Require explicit cancer context for broad, multidisciplinary journals.

    A DOI and a recent date alone are insufficient evidence that a Nature,
    Science, or general medical paper belongs in the oncology feed.
    """
    if paper.get('tier') != 'cross':
        return True
    text = ' '.join((paper.get('title') or '', paper.get('abstract') or ''))
    return bool(_ONCOLOGY_TERMS.search(text))


def rank_paper(paper):
    """A *reading priority* heuristic, NOT a probability of paper errors or acceptance."""
    tiers = {'core': 28, 'oncology': 20, 'specialist': 17, 'cross': 23}
    s = tiers.get(paper.get('tier'), 10)
    age_days = None
    if paper.get('online_date'):
        try:
            age_days = (utcnow().date() - dt.date.fromisoformat(paper['online_date'])).days
        except ValueError:
            pass
    if age_days is not None:
        s += 22 if 0 <= age_days <= 3 else 12 if 4 <= age_days <= 14 else 0
    else:
        s += 7
    text = paper.get('title', '') + ' ' + paper.get('abstract', '')
    paper['research_types'] = classify_type(text)
    s += min(20, 8 * len([k for k in paper['research_types'] if k != 'other']))
    if paper.get('abstract'):
        s += 8
    if paper.get('doi'):
        s += 8
    # PubMed explicitly labels these as non-original article types. Retain
    # them for review, but do not rank them like a research report.
    non_original = {'news', 'editorial', 'comment', 'letter', 'interview', 'newspaper article'}
    types = {str(x).casefold() for x in paper.get('publication_types', [])}
    if types & non_original:
        s -= 15
    s = max(0, s)
    paper['priority_score'] = min(s, 100)
    paper['priority_label'] = '阅读优先级，非研究缺陷或录用概率'
    paper['evidence_level'] = 'metadata_or_abstract_only'
    paper['letter_eligibility'] = 'unverified'
    return paper


def _pubmed_batches(journals, batch_size):
    for i in range(0, len(journals), batch_size):
        yield journals[i:i + batch_size]


def fetch_pubmed(journals, days=3, batch_size=12):
    """Return articles from configured journals that were created in PubMed recently."""
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
    wanted = {normalize_title(title): j for j in journals for title in [j['name'], *j.get('aliases', [])]}
    wanted_nlm = {j['nlm_id']: j for j in journals if j.get('nlm_id')}
    out = []
    for subset in _pubmed_batches(journals, batch_size):
        term = '(' + ' OR '.join('"' + j['issn'] + '"[issn]' if j.get('issn') else '"' + j['name'].replace('"', '') + '"[jour]' for j in subset) + ') AND "last ' + str(days) + ' days"[crdt]'
        params = {'db': 'pubmed', 'term': term, 'retmode': 'json', 'retmax': 500}
        if os.getenv('CONTACT_EMAIL'):
            params['email'] = os.environ['CONTACT_EMAIL']
        e = http_get_json(base + 'esearch.fcgi', params)
        search = e.get('esearchresult', {})
        ids = list(search.get('idlist', []))
        if len(set(ids)) != len(ids):
            raise RuntimeError('PubMed search returned duplicate identifiers')
        seen_ids = set(ids)
        count = int(search.get('count', len(ids)))
        if count > 10000:
            raise RuntimeError('PubMed search exceeds its 10,000-result retrieval limit; narrow the query')
        while len(ids) < count:
            time.sleep(0.4)
            page = http_get_json(base + 'esearch.fcgi', {**params, 'retstart': len(ids)})
            page_ids = page.get('esearchresult', {}).get('idlist', [])
            if not page_ids:
                raise RuntimeError('PubMed search returned an incomplete results page')
            if len(set(page_ids)) != len(page_ids) or seen_ids.intersection(page_ids):
                raise RuntimeError('PubMed search returned overlapping results pages')
            ids.extend(page_ids)
            seen_ids.update(page_ids)
        if not ids:
            continue
        for i in range(0, len(ids), 200):
            q = {'db':'pubmed', 'id': ','.join(ids[i:i+200]), 'retmode':'xml'}
            if os.getenv('CONTACT_EMAIL'):
                q['email'] = os.environ['CONTACT_EMAIL']
            xml = _request(base + 'efetch.fcgi?' + urllib.parse.urlencode(q))
            root = ET.fromstring(xml)
            for article in root.findall('.//PubmedArticle'):
                citation = article.find('MedlineCitation')
                if citation is None:
                    continue
                journal = clean_text(citation.findtext('./Article/Journal/Title'))
                nlm_id = citation.findtext('./MedlineJournalInfo/NlmUniqueID')
                j = wanted_nlm.get(nlm_id) or wanted.get(normalize_title(journal))
                if not j:
                    # NCBI can use a journal title variant, retain strict matching.
                    continue
                id_el = article.find('./MedlineCitation/PMID')
                pmid = id_el.text if id_el is not None else None
                doi = None
                for xid in article.findall('./PubmedData/ArticleIdList/ArticleId'):
                    if xid.get('IdType') == 'doi':
                        doi = xid.text
                titles = article.findall('./MedlineCitation/Article/ArticleTitle')
                title = clean_text(''.join(''.join(t.itertext()) for t in titles[0:1])) if titles else ''
                abstract_nodes = article.findall('./MedlineCitation/Article/Abstract/AbstractText')
                abstract = ' '.join(clean_text(''.join(x.itertext())) for x in abstract_nodes)
                publication_types = [clean_text(''.join(x.itertext())) for x in
                                     article.findall('./MedlineCitation/Article/PublicationTypeList/PublicationType')]
                article_dates = article.findall('./MedlineCitation/Article/ArticleDate')
                online = None
                for d in article_dates:
                    online = iso_date_from_parts([d.findtext('Year'), d.findtext('Month'), d.findtext('Day')])
                    if online:
                        break
                if not online:
                    for d in article.findall('./PubmedData/History/PubMedPubDate'):
                        if d.get('PubStatus') in ('epublish','aheadofprint'):
                            online = iso_date_from_parts([d.findtext('Year'), d.findtext('Month'), d.findtext('Day')]); break
                paper = {'doi': doi, 'pmid': pmid, 'title':title, 'abstract':abstract[:5000], 'publication_types':publication_types, 'journal':j['name'], 'tier':j['tier'], 'online_date':online, 'source':'pubmed', 'url':'https://pubmed.ncbi.nlm.nih.gov/'+str(pmid)+'/' if pmid else None}
                if relevant_to_catalog(paper):
                    out.append(rank_paper(paper))
        time.sleep(0.4)  # stay below NCBI's no-key guidelines
    return out


def fetch_crossref(journals, hours=72, per_run=12, now=None, max_publication_age_days=45):
    """Rotate Crossref checks; full roster is covered over several runs."""
    now = now or utcnow()
    cycle = int(now.timestamp() // 300)
    if not journals:
        return []
    n = min(per_run, len(journals))
    offset = (cycle * n) % len(journals)
    selected = [journals[(offset + i) % len(journals)] for i in range(n)]
    since = (now - dt.timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S')
    until = now.strftime('%Y-%m-%dT%H:%M:%S')
    out = []
    for j in selected:
        params = {
            'filter': 'from-index-date:' + since + ',until-index-date:' + until + ',type:journal-article',
            'rows': 60,
            'cursor': '*',
            'select':'DOI,title,container-title,ISSN,abstract,published-online,published,issued,URL,type'
        }
        if j.get('issn'):
            params['filter'] += ',issn:' + j['issn']
        else:
            params['query.container-title'] = j['name']
        if os.getenv('CONTACT_EMAIL'):
            params['mailto'] = os.environ['CONTACT_EMAIL']
        for m in _crossref_pages(params):
            names = m.get('container-title') or []
            accepted = {normalize_title(title) for title in [j['name'], *j.get('aliases', [])]}
            issns = m.get('ISSN') or []
            if j.get('issn') and j['issn'] not in issns:
                continue
            if not j.get('issn') and not any(normalize_title(x) in accepted for x in names):
                continue
            date = crossref_publication_date(m)
            if date and max_publication_age_days is not None:
                try:
                    age=(now.date()-dt.date.fromisoformat(date)).days
                    if age > max_publication_age_days:
                        continue
                except ValueError:
                    pass
            paper = {'doi':m.get('DOI'), 'title':clean_text((m.get('title') or [''])[0]), 'abstract':clean_text(m.get('abstract',''))[:5000], 'journal':j['name'], 'tier':j['tier'], 'online_date':date, 'source':'crossref', 'url':m.get('URL')}
            if relevant_to_catalog(paper):
                out.append(rank_paper(paper))
        time.sleep(0.15)
    return out


def _crossref_pages(params, max_pages=100):
    """Read a bounded cursor sequence; fail rather than silently truncate it."""
    params = dict(params)
    received = 0
    for _ in range(max_pages):
        message = http_get_json('https://api.crossref.org/works', params).get('message', {})
        items = message.get('items', [])
        received += len(items)
        yield from items
        if len(items) < params['rows']:
            return
        cursor = message.get('next-cursor')
        if not cursor:
            total = message.get('total-results')
            # Crossref omits next-cursor at the end, including when the last
            # page happens to contain exactly `rows` records.
            if isinstance(total, int) and received < total:
                raise RuntimeError('Crossref stopped before its reported total')
            return
        params = {**params, 'cursor': cursor}
        time.sleep(0.15)
    raise RuntimeError('Crossref pagination exceeded the per-journal safety limit')


def merge_papers(papers):
    # A PMID may arrive from one source before its DOI. Only adopt the DOI
    # when all DOI-bearing records for that PMID agree; conflicting metadata
    # must remain separate for manual verification.
    pmid_dois={}
    for paper in papers:
        if paper.get('pmid') and doi_key(paper.get('doi')):
            pmid_dois.setdefault(str(paper['pmid']),set()).add(doi_key(paper['doi']))
    merged={}
    for p in papers:
        candidates=pmid_dois.get(str(p.get('pmid') or ''),set())
        if not p.get('doi') and len(candidates)==1:
            p={**p,'doi':next(iter(candidates))}
        key = unique_id(p)
        if not key:
            continue
        prev=merged.get(key)
        if not prev:
            merged[key]=p
        else:
            # Prefer a record with an abstract; retain any missing fields from the other record.
            richer = p if len(p.get('abstract',''))>len(prev.get('abstract','')) else prev
            other = prev if richer is p else p
            merged[key] = {k: richer.get(k) or other.get(k) for k in set(richer)|set(other)}
    return list(merged.values())


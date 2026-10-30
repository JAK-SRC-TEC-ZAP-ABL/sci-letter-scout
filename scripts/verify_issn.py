"""Resolve missing journal ISSNs against Crossref's public journal catalogue.

Only exact normalized title or configured alias matches are written. Ambiguous
or unmatched titles are left untouched for manual review.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / 'config' / 'journals.json'
AUDIT = ROOT / 'data' / 'issn_audit.json'
USER_AGENT = 'SCILetterScout/0.3 (public journal metadata verification)'


def normalized(value):
    value = re.sub(r'^the\s+', '', value.casefold()).replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', '', value)


def lookup(title):
    params = urllib.parse.urlencode({'query': title, 'rows': 100})
    request = urllib.request.Request('https://api.crossref.org/journals?' + params,
                                     headers={'User-Agent': USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response).get('message', {}).get('items', [])
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    return []


def choose_issn(journal, items):
    accepted = {normalized(journal['name']), *(normalized(x) for x in journal.get('aliases', []))}
    matches = [item for item in items if normalized(item.get('title', '')) in accepted]
    issns = sorted({value for item in matches for value in item.get('ISSN', [])
                    if re.fullmatch(r'\d{4}-[\dXx]{4}', value)})
    if len(matches) != 1 or not issns:
        return None
    return issns[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='write verified ISSNs into the catalogue')
    args = parser.parse_args()
    catalogue = json.loads(CATALOGUE.read_text(encoding='utf-8'))
    audit = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
             'source': 'Crossref public journal catalogue', 'matched': [], 'unresolved': []}
    pending = [journal for journal in catalogue['journals'] if not journal.get('issn')]
    for index, journal in enumerate(pending, 1):
        try:
            issn = choose_issn(journal, lookup(journal['name']))
            if issn:
                audit['matched'].append({'name': journal['name'], 'issn': issn})
                if args.write:
                    journal['issn'] = issn
            else:
                audit['unresolved'].append({'name': journal['name'], 'reason': 'no unique exact title match'})
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            audit['unresolved'].append({'name': journal['name'], 'reason': type(error).__name__})
        if index % 10 == 0:
            print(f'checked {index}/{len(pending)}; matched {len(audit["matched"])}', flush=True)
        time.sleep(0.25)
    if args.write:
        CATALOGUE.write_text(json.dumps(catalogue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'matched {len(audit["matched"])}/{len(pending)}; unresolved {len(audit["unresolved"])}')
    for item in audit['unresolved']:
        print('unresolved:', item['name'], '-', item['reason'])


if __name__ == '__main__':
    main()


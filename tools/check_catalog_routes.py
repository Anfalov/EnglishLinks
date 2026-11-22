"""Read-only diagnostic: compare published Forever sitemaps, name tables and tooltip samples."""
import json
import re
from pathlib import Path

from build_supplements import gear_items
from data_format import name_ok
from name_data import load
from quest_sitemap import locations
from update_names import Fetcher, ROOT

KINDS = ('item', 'spell', 'achievement', 'currency', 'skill')
WWW = 'https://www.wowhead.com'
DATA = 'https://nether.wowhead.com/forever/data/'
TOOLTIP = 'https://nether.wowhead.com/forever/tooltip/'


def table(text, key):
    marker = f'WH.setPageData("{key}",'
    if text.count(marker) != 1:
        raise ValueError(f'Missing or ambiguous: {key}')
    return json.JSONDecoder().raw_decode(text.split(marker)[1].lstrip())[0]


def indexed(rows, field=None):
    result = {}
    for key, row in rows.items():
        ident = int(key)
        name = row[field] if field else row
        if field and row['id'] != ident or ident <= 0 or not name_ok(name):
            raise ValueError(f'Invalid ID/name: {key}')
        result[ident] = name
    return result


def check(fetcher, current):
    def get(url):
        return fetcher.get(url, 'catalog-route-diagnostic')

    page_urls = locations(get(WWW + '/sitemap'), 'sitemapindex', 'sitemap')
    glob = get(DATA + 'global').decode()
    versions = table(glob, 'url.dataPageVersions')
    def bundle(key):
        return get(f'{DATA}{key}?dv={int(versions[key])}').decode()

    ach = bundle('achievements')
    if not ach.startswith('var _ = g_achievements;'):
        raise ValueError('Not a Forever achievement table')
    ach_rows = {m[1]: json.JSONDecoder().raw_decode(ach, m.end())[0]
                for m in re.finditer(r'_\[(\d+)\]=(?=\{)', ach)}
    bulk = {'skill': indexed(table(glob, 'wow.skill.names')),
            'currency': indexed(table(glob, 'wow.currency.namesAndIcons'), 'name'),
            'item': gear_items(bundle('gear-planner')), 'achievement': indexed(ach_rows, 'name')}
    summary = {}
    for kind in KINDS:
        pages = [u for u in page_urls if re.fullmatch(re.escape(WWW + '/forever/sitemap/' + kind) + r'\?page=[1-9]\d*', u)]
        ids = set()
        for page in pages:
            for u in locations(get(page), 'urlset', 'url'):
                match = re.fullmatch(re.escape(WWW + '/forever/' + kind) + r'=([1-9]\d*)(?:/[^?#]*)?', u)
                if not match:
                    raise ValueError(f'Unexpected {kind} permalink: {u}')
                ids.add(int(match[1]))
        if not ids:
            raise ValueError(f'No IDs in {kind} sitemap')
        known = set(current['names']['profession' if kind == 'skill' else kind])
        names = bulk.get(kind, {})
        row = summary[kind] = dict(sitemap=len(ids), new_to_addon=len(ids-known), known_outside_map=len(known-ids),
                                   bulk_total=len(names), bulk_in_sitemap=len(ids & names.keys()), samples={})
        if kind == 'skill':
            row['alchemy'] = names.get(171)
            if not ids <= names.keys() or row['alchemy'] != 'Alchemy':
                raise ValueError('Skill names do not cover the sitemap')
        else:
            canonical = {'item': 6948, 'spell': 133, 'achievement': 63969, 'currency': 3468}[kind]
            candidates = (ids-known-names.keys()) or (ids-names.keys()) or ids
            for ident in sorted({canonical, max(candidates)}):
                raw = json.loads(get(f'{TOOLTIP}{kind}/{ident}?locale=0'))
                if not isinstance(raw.get('name'), str) or not name_ok(raw['name']):
                    raise ValueError(f'Invalid {kind} tooltip: {ident}')
                row['samples'][ident] = raw['name']
        print(f'{kind}: {json.dumps(row, ensure_ascii=False)}', flush=True)
    return summary


if __name__ == '__main__':
    out = Path('wowhead-check/catalogs')
    fetcher = Fetcher(out)
    try:
        report = check(fetcher, load(ROOT / 'EnglishLinks/NameData.lua'))
        (out / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        (out / 'requests.json').write_text(json.dumps(fetcher.records, indent=2))

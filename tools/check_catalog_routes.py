"""Read-only diagnostic: compare published Forever sitemaps, name tables and tooltip samples."""
import json
from pathlib import Path

from catalog_sources import bulk, discover, TYPES
from data_format import name_ok
from name_data import load
from update_names import Fetcher, ROOT

TOOLTIP = 'https://nether.wowhead.com/forever/tooltip/'


def check(fetcher, current):
    def get(url):
        return fetcher.get(url, 'catalog-route-diagnostic')

    kinds = tuple(k for k in TYPES if k != 'quest')
    outcomes = []
    maps = discover(fetcher, outcomes, kinds)
    names_by_kind = {k: rows for part in bulk(fetcher, outcomes) for k, rows in part['names'].items()}
    if any(row['status'] != 'parsed' for row in outcomes):
        raise ValueError(f'Incomplete catalog diagnostics: {outcomes}')
    summary = {}
    for internal in kinds:
        kind = TYPES[internal]
        ids = maps[internal]
        known = set(current['names']['profession' if kind == 'skill' else kind])
        names = names_by_kind.get(internal, {})
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

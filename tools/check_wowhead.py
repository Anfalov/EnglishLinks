#!/usr/bin/env python3
"""Read-only connectivity and parser check using the production downloader."""
import json
from pathlib import Path
import sys

import update_names as update
import quest_sitemap


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'wowhead-check'
    fetcher = update.Fetcher(output)
    if '--sitemap' in sys.argv:
        url = quest_sitemap.PAGE + '1'
        try:
            ids = quest_sitemap.quest_ids(fetcher.get(url, 'wowhead-quest-sitemap'))
            print(f'{url}: {len(ids)} distinct Forever quest IDs ({min(ids)}..{max(ids)})')
            return 0
        finally:
            report = {'downloads': fetcher.records}
            (output / 'sitemap-report.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report), flush=True)
    if '--quest-fallback' in sys.argv:
        current = update.named('quest', {7: 'Old title', 1425: 'Deliver the Shipment'})
        additional = [('ID discovery fixture', update.named('quest', {92485: 'Untrusted title'}))]
        outcomes = []
        primary = update.quest_tooltips(fetcher, current, update.empty(), additional, outcomes)
        merged, changes = update.name_data.merge(current, primary, additional)
        expected = {7: 'Kobold Camp Cleanup', 1425: 'Deliver the First Shipment',
                    92485: 'A Student of Nature'}
        passed = merged['names']['quest'] == expected and all(c['source'] == 'wowhead' for c in changes)
        report = {'passed': passed, 'names': merged['names']['quest'],
                  'checks': outcomes, 'downloads': fetcher.records}
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report), flush=True)
        return 0 if passed else 1
    manifest = json.loads((root / 'data/wowhead-sources/manifest.json').read_text())['files']
    if '--tooltips' in sys.argv:
        entries = [dict(parser='tooltip', kind=kind, id=identifier,
                        url=f'https://nether.wowhead.com/forever/tooltip/{kind}/{identifier}?locale=0')
                   for kind, identifier in [('quest', 7), ('quest', 1425), ('quest', 92485),
                                            ('item', 6948), ('spell', 133)]]
    else:
        entries = [next(e for e in manifest if e.get('kind') == kind and e['parser'] == 'list')
                   for kind in ('quest', 'item')]
        entries.append(next(e for e in manifest if e['parser'] == 'mounts'))
    outcomes = []
    for entry in entries:
        url = update.fresh_url(entry['url'])
        result = {'url': url}
        try:
            raw = fetcher.get(url, 'wowhead-forever')
            if entry['parser'] == 'tooltip':
                data = json.loads(raw)
                if data.get('error'):
                    raise ValueError(str(data['error']))
                parsed = update.named(entry['kind'], {entry['id']: data['name']})
                result['name'] = data['name']
            else:
                parsed = update.parse_wowhead(entry, raw)
            result.update(status='parsed', counts={k: len(v) for k, v in parsed['names'].items()})
        except Exception as error:
            result.update(status='failed', error=str(error))
        outcomes.append(result)
        print(json.dumps(result), flush=True)
    report = {'checks': outcomes, 'downloads': fetcher.records}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for record in fetcher.records:
        print(json.dumps({k: v for k, v in record.items() if k != 'archive_member'}), flush=True)
    return 0 if all(r['status'] == 'parsed' for r in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())

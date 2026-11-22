#!/usr/bin/env python3
"""Read-only connectivity and parser check using the production downloader."""
import json
from pathlib import Path
import sys

import update_names as update


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'wowhead-check'
    fetcher = update.Fetcher(output)
    manifest = json.loads((root / 'data/wowhead-sources/manifest.json').read_text())['files']
    entries = [next(e for e in manifest if e.get('kind') == kind and e['parser'] == 'list')
               for kind in ('quest', 'item')]
    entries.append(next(e for e in manifest if e['parser'] == 'mounts'))
    outcomes = []
    for entry in entries:
        url = update.fresh_url(entry['url'])
        result = {'url': url}
        try:
            raw = fetcher.get(url, 'wowhead-forever')
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

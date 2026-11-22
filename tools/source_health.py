"""Summarize incomplete checks for humans and the independent Actions alert job."""
from collections import Counter
import json
import os
import re
from urllib.parse import urlsplit


def problems(rows):
    counts = Counter()
    for row in rows:
        status = row['status']
        if status == 'parsed':
            if row.get('freshness') != 'pinned-fallback':
                continue
            status = 'pinned-fallback'
        reason = row.get('reason', '')
        code = re.search(r'HTTP(?: Error)? (\d{3})', reason)
        host = urlsplit(row.get('url', '')).hostname or ''
        counts[(row['source'], host, status, 'HTTP ' + code[1] if code else reason[:160])] += 1
    return counts


def main():
    with open('update-results/report.json') as report:
        data = json.load(report)
    counts = problems(data['sources'])
    scans = [r for r in data['sources'] if r['source'].endswith('-tooltip') and 'total' in r]
    def total(field):
        return sum(r[field] for r in scans)
    coverage = (f"Tooltips {total('parsed')}/{total('total')}; "
                f"not requested {total('not_requested')}; failed {total('failed')}") if scans else ''
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        print('coverage=' + coverage, file=output)
        print('changed=' + str(data['changed']).lower(), file=output)
        print('degraded=' + str(bool(counts)).lower(), file=output)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        print(f"Name changes: {len(data['changes'])}", file=summary)
        if coverage:
            print(coverage, file=summary)
            print(coverage)
            for r in scans:
                line = (f"{r['source']}: {r['parsed']}/{r['total']}; "
                        f"not requested {r['not_requested']}; failed {r['failed']}; "
                        f"new IDs not requested {r['missing_unrequested']}/{r['missing_total']}")
                print('- ' + line, file=summary)
                print(line)
        if counts:
            print('\nIncomplete source checks (see report.json for URLs):\n', file=summary)
        for (source, host, status, reason), count in sorted(counts.items()):
            print(f'- {source} {host}: {status} × {count} — {reason}', file=summary)


if __name__ == '__main__':
    main()

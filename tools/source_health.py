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
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        print('changed=' + str(data['changed']).lower(), file=output)
        print('degraded=' + str(bool(counts)).lower(), file=output)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        print(f"Name changes: {len(data['changes'])}", file=summary)
        if counts:
            print('\nIncomplete source checks (see report.json for URLs):\n', file=summary)
        for (source, host, status, reason), count in sorted(counts.items()):
            print(f'- {source} {host}: {status} × {count} — {reason}', file=summary)


if __name__ == '__main__':
    main()

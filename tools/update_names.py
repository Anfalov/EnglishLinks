#!/usr/bin/env python3
"""Refresh the installed dictionary; unavailable sources never erase old names."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import build_wowhead as wh
import build_random_affixes as rand
import build_supplements as supplements
import build_quests as quests
from data_format import name_ok
import name_data

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


class SourceBlockedError(RuntimeError):
    def __init__(self, host, code):
        self.code = code
        super().__init__(f'{host}: requests stopped after HTTP {code} in this run')


class Fetcher:
    def __init__(self, output):
        self.output = output
        self.records = []
        self.lock = threading.Lock()
        self.blocked_hosts = {}
        (output / 'raw').mkdir(parents=True, exist_ok=True)

    def save_response(self, record, response, raw):
        # Keep only diagnostic headers, never cookies or authorization details.
        record.update(status=response.status, final_url=response.url,
                      response_headers={name: response.headers[name] for name in (
                          'Content-Type', 'Server', 'X-Cache', 'X-Amzn-Waf-Action', 'Retry-After'
                      ) if response.headers.get(name) is not None})
        digest = hashlib.sha256(raw).hexdigest()
        record.update(retrieved_at=now(), sha256=digest, size_bytes=len(raw),
                      archive_member='raw/' + digest)
        with self.lock:
            (self.output / record['archive_member']).write_bytes(raw)

    def get(self, url, source, version=None, build=None):
        record = dict(url=url, source_id=source, source_version=version,
                      game_build=build, locale='enUS', retrieval_started_at=now())
        try:
            host = urllib.parse.urlsplit(url).hostname
            with self.lock:
                if host in self.blocked_hosts:
                    record['request_skipped'] = True
                    raise SourceBlockedError(host, self.blocked_hosts[host])
            request = urllib.request.Request(url, headers={'User-Agent': 'EnglishLinks source updater'})
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(50 * 1024 * 1024 + 1)
                record.update(status=response.status, final_url=response.url)
                if len(raw) > 50 * 1024 * 1024:
                    raise ValueError('Response exceeds 50 MiB')
                self.save_response(record, response, raw)
            return raw
        except urllib.error.HTTPError as error:
            host = urllib.parse.urlsplit(error.url).hostname
            if host in ('www.wowhead.com', 'nether.wowhead.com') and error.code in (403, 429):
                with self.lock:
                    self.blocked_hosts[host] = error.code
            record.update(status=error.code, final_url=error.url,
                          failed_at=now(), error=str(error))
            try:
                with error:
                    raw = error.read(64 * 1024 + 1)
                    record['body_truncated'] = len(raw) > 64 * 1024
                    # The workflow retains report.json even when names did not
                    # change, so include enough text to identify the error page.
                    record['error_body_preview'] = raw[:4096].decode('utf-8', errors='replace')
                    self.save_response(record, error, raw[:64 * 1024])
            except Exception as diagnostic_error:
                # Failure to save diagnostics must not obscure the HTTP error.
                record['diagnostic_error'] = str(diagnostic_error)
            raise
        except Exception as error:
            record.update(failed_at=now(), error=str(error))
            raise
        finally:
            with self.lock:
                self.records.append(record)


def empty():
    return {'names': {}, 'bonuses': {}, 'random_affixes': {}}


def parse_wowhead(entry, raw):
    text = raw.decode('utf-8')
    result = empty()
    parser = entry['parser']
    def add(kind, key, value):
        wh.insert(result['names'].setdefault(kind, {}), key, value)
    if parser == 'list':
        rows = wh.list_rows(text, entry['category'])
        for row in rows:
            if 'lo' in entry and not entry['lo'] <= int(row['id']) <= entry['hi']:
                raise ValueError('Ignored ID filter')
            add(entry['kind'], row['id'], row.get('name', row.get('name_@locale@')))
    elif parser == 'gatherer':
        match = re.search(r'WH.Gatherer.addData\(3,\s*16,\s*', text)
        if not match:
            raise ValueError('Not a Forever gatherer response')
        for key, row in wh.decode(wh.literal(text, match.end())).items():
            add('item', key, row['name_enus'])
    elif parser == 'spell':
        match = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if not match or 'dataEnv' not in text:
            raise ValueError('Missing spell page title')
        add('spell', entry['id'], html.unescape(match[1]))
    elif parser == 'pets':
        for match in re.finditer(r'g_battlepets\[\d+\]\s*=\s*', text):
            row = wh.decode(wh.literal(text, match.end()))
            add('companion', row['species'], row['name'])
    elif parser == 'mounts':
        match = re.search(r'var g_mounts\s*=\s*', text)
        for key, row in wh.decode(wh.literal(text, match.end())).items():
            if int(key) != row['id']:
                raise ValueError('Mount ID mismatch')
            add('mount', key, row['name'])
    elif parser == 'bonuses':
        result['bonuses'] = wh.parse_bonuses(text)
    elif parser == 'randomEnchant':
        result['random_affixes'] = rand.parse(text)
    else:
        raise ValueError('Unknown Wowhead parser')
    name_data.validate(result)
    return result


def combine_primary(parts):
    """Disagreeing simultaneous responses cannot silently win by load order."""
    result, conflicts = empty(), set()
    for part in parts:
        for section in result:
            groups = part.get(section, {})
            groups = groups.items() if section == 'names' else [(section, groups)]
            for kind, rows in groups:
                target = result['names'].setdefault(kind, {}) if section == 'names' else result[section]
                for key, value in rows.items():
                    identity = (section, kind, key)
                    if identity in conflicts:
                        continue
                    if key in target and target[key] != value:
                        del target[key]
                        conflicts.add(identity)
                    else:
                        target[key] = value
    return result, sorted(conflicts)


def fresh_url(url):
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k not in ('db', 'versionsSig')]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query, safe=':;,=')))


def wowhead(fetcher, current, root, outcomes):
    entries = json.loads((root / 'data/wowhead-sources/manifest.json').read_text())['files']
    entry = next(e for e in json.loads((root / 'data/random-affix-sources/manifest.json').read_text())['files']
                 if e['parser'] == 'randomEnchant')
    entries = entries + [entry]

    def read(entry, depth=0):
        url = fresh_url(entry['url'])
        try:
            raw = fetcher.get(url, 'wowhead-forever')
            try:
                parsed = parse_wowhead(entry, raw)
            except ValueError as error:
                if 'Truncated' not in str(error) or 'lo' not in entry or depth >= 32:
                    raise
                lo, hi = entry['lo'], entry['hi']
                if lo >= hi:
                    raise
                mid = (lo + hi) // 2
                children = []
                for low, high in [(lo, mid), (mid + 1, hi)]:
                    child = dict(entry, lo=low, hi=high)
                    child['url'] = re.sub(r';2:4;\d+:\d+', f';2:4;{low}:{high}', entry['url'])
                    if child['url'] == entry['url']:
                        raise ValueError('Cannot split capped list URL')
                    children.extend(read(child, depth + 1))
                return children
            outcomes.append(dict(source='wowhead-forever', url=url, status='parsed'))
            return [parsed]
        except Exception as error:
            outcomes.append(dict(source='wowhead-forever', url=url, status='skipped', reason=str(error)))
            return []

    with ThreadPoolExecutor(max_workers=4) as pool:
        parts = [part for batch in pool.map(read, entries) for part in batch]
    primary, conflicts = combine_primary(parts)
    # Also refresh item IDs acquired from supplements on earlier runs.
    missing = sorted(current['names'].get('item', {}).keys() - primary['names'].get('item', {}).keys())
    for start in range(0, len(missing), 100):
        ids = ','.join(map(str, missing[start:start + 100]))
        parts.extend(read(dict(parser='gatherer', url='https://www.wowhead.com/forever/gatherer?items=' + ids)))
    primary, conflicts = combine_primary(parts)
    if conflicts:
        outcomes.append(dict(source='wowhead-forever', status='conflicts-kept-current', ids=conflicts))
    return primary


def named(kind, rows):
    result = dict(empty(), names={kind: rows})
    name_data.validate(result)
    return result


def quest_tooltips(fetcher, current, primary, additional, outcomes, interval=0.25):
    """Confirm known quest IDs through Wowhead's public English tooltip service.

    List pages discover IDs; this endpoint only answers IDs we already know.
    Supplemental names do not overwrite anything: only their IDs are consulted
    here, before the final primary-first merge.
    """
    candidates = set(current['names'].get('quest', {}))
    for _, data in additional:
        candidates.update(data.get('names', {}).get('quest', {}))
    candidates.difference_update(primary['names'].get('quest', {}))
    if not candidates:
        return primary
    stop = threading.Event()
    lock = threading.Lock()
    next_request = 0.0
    counts = dict(requested=0, parsed=0, failed=0, not_requested=0)

    def read(identifier):
        nonlocal next_request
        with lock:
            if stop.is_set():
                counts['not_requested'] += 1
                return None
            delay = next_request - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            next_request = time.monotonic() + interval
            counts['requested'] += 1
        url = f'https://nether.wowhead.com/forever/tooltip/quest/{identifier}?locale=0'
        try:
            raw = fetcher.get(url, 'wowhead-forever-quest-tooltip')
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get('error') or 'name' not in data:
                raise ValueError('Missing quest tooltip name')
            parsed = named('quest', {identifier: data['name']})
            with lock:
                counts['parsed'] += 1
            return parsed
        except Exception as error:
            # Do not keep sending requests to an endpoint that refuses access
            # or asks us to slow down. Existing names remain intact.
            if isinstance(error, (urllib.error.HTTPError, SourceBlockedError)) and error.code in (403, 429):
                stop.set()
            with lock:
                counts['failed'] += 1
                outcomes.append(dict(source='wowhead-forever-quest-tooltip', url=url,
                                     status='skipped', reason=str(error)))
            return None

    print(f'Checking {len(candidates)} known quest IDs via Wowhead tooltips...', flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        parts = [part for part in pool.map(read, sorted(candidates)) if part is not None]
    updated, conflicts = combine_primary([primary] + parts)
    if conflicts:
        raise ValueError('Unexpected quest tooltip conflict')
    outcomes.append(dict(source='wowhead-forever-quest-tooltip',
                         status='partial' if counts['failed'] or counts['not_requested'] else 'parsed',
                         reason='Known IDs only; list-page discovery may be unavailable', **counts))
    return updated


def petscout_archive(raw):
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ValueError('PetScout download is not a ZIP archive')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        member = 'PetScoutForever/data/locations.lua'
        if archive.namelist().count(member) != 1:
            raise ValueError('PetScout archive must contain one locations.lua')
        info = archive.getinfo(member)
        if info.file_size > 10 * 1024 * 1024:
            raise ValueError('PetScout member exceeds limit')
        text = archive.read(info).decode('utf-8')
    build = re.search(r'build (1\.60\.\d+\.\d+)', text)
    if not build:
        raise ValueError('Not a Forever PetScout source')
    return named('companion', supplements.petscout_names(text, 'Locations', build[1]))


def petscout_file_url(page, file_id):
    # The file detail page publishes the actual ZIP name. Never infer a version
    # from the display title or accept an arbitrary download host from HTML.
    page = html.unescape(page).replace('\\"', '"')
    match = re.search(r'"fileName"\s*:\s*"(PetScoutForever-[^"<>/\\]+\.zip)"', page)
    if not match:
        visible = re.sub(r'<[^>]+>', ' ', page)
        match = re.search(r'File name\s+(PetScoutForever-[^\s<>/\\]+\.zip)', visible)
    if not match:
        raise ValueError('PetScout file page has no ZIP filename')
    filename = urllib.parse.quote(match[1], safe='')
    return f'https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000:03d}/{filename}'


def petscout(fetcher, root, outcomes):
    manifest = json.loads((root / 'data/supplement-sources/manifest.json').read_text())
    pinned = next(e for e in manifest if e['file'] == 'petscout-locations.lua')
    pinned_id = int(pinned['url'].rstrip('/').rsplit('/', 1)[1])
    candidates = []
    discovered = False
    try:
        page = fetcher.get('https://www.curseforge.com/wow/addons/petscout-forever/files/all',
                           'petscout-discovery').decode('utf-8').replace('\\/', '/')
        ids = re.findall(r'/wow/addons/petscout-forever/files/(\d+)', page)
        if not ids:
            raise ValueError('PetScout file list is empty or unavailable')
        latest = max(map(int, ids))
        if latest < pinned_id:
            raise ValueError('PetScout file list is older than the pinned release')
        if latest == pinned_id:
            candidates.append((latest, pinned['download_url']))
        else:
            detail = fetcher.get(f'https://www.curseforge.com/wow/addons/petscout-forever/files/{latest}',
                                 'petscout-discovery', str(latest)).decode('utf-8')
            candidates.append((latest, petscout_file_url(detail, latest)))
        discovered = True
    except Exception as error:
        outcomes.append(dict(source='petscout-discovery', status='skipped', reason=str(error)))

    # Keep the known official archive usable even when CurseForge's web pages
    # are unavailable. The report distinguishes fallback data from a fresh check.
    if not candidates or candidates[0][0] != pinned_id:
        candidates.append((pinned_id, pinned['download_url']))
    for index, (file_id, url) in enumerate(candidates):
        try:
            raw = fetcher.get(url, 'petscout', str(file_id))
            if file_id == pinned_id and hashlib.sha256(raw).hexdigest() != pinned['archive_sha256']:
                raise ValueError('Pinned PetScout archive checksum mismatch')
            parsed = petscout_archive(raw)
            outcomes.append(dict(source='petscout', url=url, version=str(file_id), status='parsed',
                                 freshness='latest-listed' if discovered and index == 0 else 'pinned-fallback'))
            return parsed
        except Exception as error:
            outcomes.append(dict(source='petscout', url=url, version=str(file_id), status='skipped', reason=str(error)))
    return None


def other_sources(fetcher, root, outcomes):
    result = []
    def attempt(source, url, parser, version=None, game_build=None):
        try:
            parsed = parser(fetcher.get(url, source, version, game_build))
            result.append((source, parsed))
            outcomes.append(dict(source=source, url=url, status='parsed'))
        except Exception as error:
            outcomes.append(dict(source=source, url=url, status='skipped', reason=str(error)))

    entries = json.loads((root / 'data/quest-sources/manifest.json').read_text())
    priority = ['questiedb/foreverBaseQuest.lua', 'questiedb/foreverQuestDB.lua',
                'EverythingQuests/QuestAvailable_Forever.lua', 'Completao/ForeverNew.lua']
    entries.sort(key=lambda entry: priority.index(entry['file']))
    entries += [dict(repository='Questie/QuestieDB', path='src/corrections/Forever/generated/foreverBaseItem.lua', parser='items'),
                dict(repository='ElliotWood/Forever', path='assets/db_inputs/wowhead_forever_gearplanner.txt', parser='gear')]
    heads = {}
    for e in entries:
        repo = e['repository']
        if repo not in heads:
            try:
                heads[repo] = json.loads(fetcher.get(f'https://api.github.com/repos/{repo}/commits/HEAD', repo))['sha']
                if not re.fullmatch(r'[0-9a-f]{40}', heads[repo]):
                    raise ValueError('Invalid commit SHA')
            except Exception as error:
                heads[repo] = None
                outcomes.append(dict(source=repo, status='skipped', reason=str(error)))
        if not heads[repo]:
            continue
        sha = heads[repo]
        def parse(raw, entry=e):
            text = raw.decode('utf-8')
            if entry.get('parser') == 'items':
                return named('item', supplements.questie_items(text))
            if entry.get('parser') == 'gear':
                return named('item', supplements.gear_items(text))
            return named('quest', quests.extract(text, entry['file']))
        attempt(repo, f'https://raw.githubusercontent.com/{repo}/{sha}/{e["path"]}', parse, version=sha)

    try:
        index = fetcher.get('https://thewowdb.com/wow-forever/currencies/', 'thewowdb').decode('utf-8')
        paths = sorted(set(re.findall(r'href="(/wow-forever/currency/[^" ]+)"', index)))
        for path in paths:
            key = int(re.search(r'-(\d+)/$', path)[1])
            def currency(raw, key=key):
                text = raw.decode('utf-8')
                title = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
                return named('currency', {key: html.unescape(title[1])})
            attempt('thewowdb', 'https://thewowdb.com' + path, currency)
    except Exception as error:
        outcomes.append(dict(source='thewowdb', status='skipped', reason=str(error)))

    pet_result = petscout(fetcher, root, outcomes)
    if pet_result is not None:
        result.append(('petscout', pet_result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT / 'update-results')
    parser.add_argument('--apply', action='store_true', help='Write accepted changes; no Git operations')
    parser.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_id):
        parser.error('Invalid run ID')
    path = args.root / 'EnglishLinks/NameData.lua'
    current = name_data.load(path)
    args.output.mkdir(parents=True, exist_ok=True)
    fetcher, outcomes = Fetcher(args.output), []
    print('Checking Wowhead Forever...', flush=True)
    primary = wowhead(fetcher, current, args.root, outcomes)
    print('Checking supplemental sources...', flush=True)
    additional = other_sources(fetcher, args.root, outcomes)
    primary = quest_tooltips(fetcher, current, primary, additional, outcomes)
    updated, changes = name_data.merge(current, primary, additional)
    report = dict(starting_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  finished_at=now(), changed=bool(changes), changes=changes,
                  sources=outcomes, downloads=fetcher.records)
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if args.apply and changes:
        destination = args.root / 'data/auto-updates' / args.run_id
        destination.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(destination / 'sources.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for raw in sorted((args.output / 'raw').iterdir()):
                archive.write(raw, 'raw/' + raw.name)
        shutil.copy2(args.output / 'report.json', destination / 'report.json')
        (destination / 'before.lua').write_bytes(path.read_bytes())
        path.write_text(name_data.render(updated))
        registry_path = args.root / 'data/source-registry.json'
        registry = json.loads(registry_path.read_text())
        registry.setdefault('automatic_updates', []).append(dict(
            id=args.run_id, report=str((destination / 'report.json').relative_to(args.root)),
            archive=str((destination / 'sources.zip').relative_to(args.root)),
            archive_sha256=hashlib.sha256((destination / 'sources.zip').read_bytes()).hexdigest(),
            before_sha256=report['starting_sha256'], after_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(changed=bool(changes), additions=sum(c['before'] is None for c in changes),
                          renamed=sum(c['before'] is not None for c in changes),
                          skipped=sum(s['status'] == 'skipped' for s in outcomes))))


if __name__ == '__main__':
    main()

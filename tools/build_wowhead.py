#!/usr/bin/env python3
"""Rebuild the authoritative Forever overlay from hash-checked Wowhead snapshots.
No downloaded JavaScript or Lua is executed. Other packs are fallback inputs;
this pack loads last and overwrites their titles for every observed Wowhead ID.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import zipfile
from data_format import name_ok, lua


def literal(text, start):
    depth, quote, escaped = 0, None, False
    for i in range(start, len(text)):
        c = text[i]
        if quote:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == quote:
                quote = None
        elif c in '\"\'':
            quote = c
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError('Unclosed data literal')


def decode(text):
    # Only normalize syntax outside strings; json.loads rejects executable code.
    tokens = re.split(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', text)
    for i in range(0, len(tokens), 2):
        tokens[i] = re.sub(r'([,{]\s*)([A-Za-z_$][\w$]*|-?\d+)\s*:', r'\1"\2":', tokens[i])
        tokens[i] = re.sub(r',\s*([}\]])', r'\1', tokens[i])
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result and (k.isdigit() or k in ('id', 'name', 'name_enus', 'species')):
                raise ValueError('Duplicate data key: ' + k)
            result[k] = v
        return result
    return json.loads(''.join(tokens), object_pairs_hook=unique)


def list_rows(text, category):
    m = re.search(r'<script type="application/json" id="data.page.listPage.listviews">(.*?)</script>', text, re.S)
    if m:
        view = next(v for v in json.loads(m[1]) if v['id'] == category)
        if view.get('_truncated'):
            raise ValueError('Truncated list: ' + category)
        return view['data']
    if '_truncated: 1' in text:
        raise ValueError('Truncated list: ' + category)
    pattern = (r'var listview' + category + r'\s*=\s*' if category in ('items', 'spells')
               else r"new Listview\(\{template: 'quest'.*?data:\s*")
    m = re.search(pattern, text, re.S)
    if not m:
        raise ValueError('Missing list: ' + category)
    return decode(literal(text, m.end()))


def insert(names, key, value):
    key = int(key)
    if not 0 < key <= 2147483647 or not name_ok(value):
        raise ValueError('Unsafe ID/title: ' + str(key))
    if key in names and names[key] != value:
        raise ValueError('Conflicting Wowhead titles: ' + str(key))
    names[key] = value


def parse_bonuses(text):
    m = re.search(r'var g_itembonuses\s*=\s*', text)
    bonuses = decode(literal(text, m.end()))
    m = re.search(r"WH.setPageData\(\s*[\"']wow.item.bonusNameDescriptions[\"'],\s*", text)
    descriptions = decode(literal(text, m.end()))
    result = {}
    for key, effects in bonuses.items():
        if int(key) <= 0:
            continue
        suffixes = {descriptions[str(e[1])]['name'] for e in effects if e[0] == 5}
        if len(suffixes) > 1:
            raise ValueError('Ambiguous suffix for bonus ' + key)
        value = next(iter(suffixes), '')
        if value and not name_ok(value):
            raise ValueError('Unsafe item suffix')
        # Effect 4 is a tooltip tag, NOT a prefix to the item name.
        # Group indirections are not expanded here; preserve those links.
        if not any(e[0] == 33 for e in effects):
            result[int(key)] = value
    return result


def compile_snapshot(directory, _seen=None):
    directory = directory.resolve()
    seen = set() if _seen is None else set(_seen)
    if directory in seen:
        raise ValueError('Cyclic Wowhead snapshot history')
    seen.add(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    archive = directory / 'snapshot.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Wowhead archive checksum mismatch')
    names = {k: {} for k in ('item', 'spell', 'quest', 'profession', 'achievement', 'currency', 'companion', 'mount')}
    ranges = {c: [] for c in ('items', 'quests', 'spells')}
    bonuses = {}
    with zipfile.ZipFile(archive) as z:
        for entry in manifest['files']:
            raw = z.read(entry['file'])
            if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('Source checksum mismatch: ' + entry['file'])
            text = raw.decode('utf-8')
            parser, kind = entry['parser'], entry.get('kind')
            if parser == 'list':
                rows = list_rows(text, entry['category'])
                if 'lo' in entry:
                    lo, hi = entry['lo'], entry['hi']
                    ranges[entry['category']].append((lo, hi))
                    if not all(lo <= int(r['id']) <= hi for r in rows):
                        raise ValueError('Ignored ID filter')
                for r in rows:
                    insert(names[kind], r['id'], r.get('name', r.get('name_@locale@')))
            elif parser == 'gatherer':
                m = re.search(r'WH.Gatherer.addData\(3,\s*16,\s*', text)
                if not m:
                    raise ValueError('Not a Forever item response')
                for key, r in decode(literal(text, m.end())).items():
                    insert(names['item'], key, r['name_enus'])
            elif parser == 'spell':
                m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
                insert(names['spell'], entry['id'], html.unescape(m[1]))
            elif parser == 'pets':
                for m in re.finditer(r'g_battlepets\[\d+\]\s*=\s*', text):
                    row = decode(literal(text, m.end()))
                    insert(names['companion'], row['species'], row['name'])
            elif parser == 'mounts':
                m = re.search(r'var g_mounts\s*=\s*', text)
                for key, r in decode(literal(text, m.end())).items():
                    if int(key) != r['id']:
                        raise ValueError('Mount spell ID mismatch')
                    insert(names['mount'], key, r['name'])
            elif parser == 'bonuses':
                bonuses = parse_bonuses(text)
            else:
                raise ValueError('Unknown snapshot parser')
    for category, spans in ranges.items():
        spans.sort()
        if not spans or spans[0][0] != 0 or spans[-1][1] != 2147483647 or any(a[1] + 1 != b[0] for a, b in zip(spans, spans[1:])):
            raise ValueError('Incomplete or overlapping ranges: ' + category)
    if any(not values for values in names.values()) or not bonuses:
        raise ValueError('Empty Wowhead category')
    # A missing row is not evidence that a name was removed from the game.
    # Keep previously observed Wowhead names, while every fresh name wins.
    if manifest.get('previous_snapshot'):
        previous, old_bonuses, _ = compile_snapshot(directory / manifest['previous_snapshot'], seen)
        for kind, rows in previous.items():
            for key, value in rows.items():
                names[kind].setdefault(key, value)
        for key, value in old_bonuses.items():
            bonuses.setdefault(key, value)
    return names, bonuses, manifest


def render(names, bonuses, manifest):
    lines = ['-- Generated by tools/build_wowhead.py; authoritative Wowhead Forever names.',
             'local _, ns = ...', 'local primary = ' + lua(names),
             'for kind, entries in pairs(primary) do',
             '    ns.Names[kind] = ns.Names[kind] or {}',
             '    for id, name in pairs(entries) do ns.Names[kind][id] = name end',
             '    local count, primaryCount = 0, 0',
             '    for _ in pairs(ns.Names[kind]) do count = count + 1 end',
             '    for _ in pairs(entries) do primaryCount = primaryCount + 1 end',
             '    ns.PackMeta[kind] = {count=count, primaryCount=primaryCount,',
             '        fallbackCount=count-primaryCount, locale="enUS",',
             '        coverage="wowhead-forever-primary", sourceDate="' + manifest['retrieved_date'] + '"}',
             'end', 'ns.ItemBonusSuffixes = ' + lua(bonuses), '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', type=Path, default=Path('data'))
    p.add_argument('--output', type=Path, default=Path('dist/WowheadNames_enUS.lua'))
    args = p.parse_args()
    names, bonuses, manifest = compile_snapshot(args.data_dir / 'wowhead-sources')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(names, bonuses, manifest), encoding='utf-8')
    from build_quests import compile_quests
    from build_supplements import compile_supplements
    fallback = {'quest': compile_quests(args.data_dir / 'quest-sources')[0]}
    for kind, rows in compile_supplements(args.data_dir)[0].items():
        for key, value in rows.items():
            fallback.setdefault(kind, {}).setdefault(key, value)
    report = {'policy': 'Wowhead Forever wins every name conflict; other sources fill missing IDs only.', 'categories': {}}
    for kind, rows in names.items():
        old = fallback.get(kind, {})
        report['categories'][kind] = {'wowhead': len(rows), 'fallback': len(old.keys() - rows.keys()), 'total': len(old.keys() | rows.keys()),
            'overwritten': [{'id': k, 'fallback': old[k], 'wowhead': v} for k, v in sorted(rows.items()) if k in old and old[k] != v]}
    report['item_bonuses'] = {'known': len(bonuses), 'with_suffix': sum(bool(v) for v in bonuses.values()), 'distinct_suffixes': len(set(bonuses.values()) - {''})}
    (args.data_dir / 'wowhead-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: {f:v for f,v in r.items() if f != 'overwritten'} for k,r in report['categories'].items()}))
    print('Item bonuses:', report['item_bonuses'])


if __name__ == '__main__':
    main()

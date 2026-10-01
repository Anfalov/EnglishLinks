#!/usr/bin/env python3
"""Offline Forever name supplements. Parse pinned snapshots; never execute them."""
import csv
import hashlib
import json
from pathlib import Path
import re
from build_names import lua_string
from build_packs import name_ok, number

STRING = r'("(?:\\.|[^"\\])*")'


def insert(names, key, value):
    key = number(key)
    if not name_ok(value):
        raise ValueError('Unsafe name for %s' % key)
    if key in names and names[key] != value:
        raise ValueError('Conflicting duplicate %s' % key)
    names[key] = value


def questie_items(text):
    names = {}
    pattern = r'^\s*\[(\d+)\]\s*=\s*\{[^\n]*\n\s*\[itemKeys.name\]\s*=\s*' + STRING
    explicit = re.findall(pattern, text, re.M)
    if len(explicit) != text.count('[itemKeys.name]'):
        raise ValueError('Unparsed Questie item name')
    for key, token in explicit:
        insert(names, key, json.loads(token))
    # Generated comments retain reviewed Forever Wowhead IDs/titles even when
    # the correction only adds a vendor/reward and inherits its name elsewhere.
    pattern = r'^        \[(\d+)\] = \{ -- (.+?) : https://wowhead.com/forever/item=(\d+)/[^\n]*$'
    for key, value, url_id in re.findall(pattern, text, re.M):
        if key != url_id:
            raise ValueError('Questie comment URL/row ID mismatch')
        insert(names, key, value)
    return names


def gear_items(text):
    prefix = 'WH.setPageData("wow.gearPlanner.classicplus.item", '
    if not text.startswith(prefix):
        raise ValueError('Not the Forever item snapshot')
    end = text.index('\n});', len(prefix))
    body = text[len(prefix):end] + '\n}'
    # Upstream uses one trailing comma at the end of this JavaScript object.
    body = re.sub(r',\s*}$', '}', body)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    rows = json.loads(body, object_pairs_hook=unique)
    names = {}
    for key, row in rows.items():
        if row['versionNum'] != 16001 or int(key) != row['id']:
            raise ValueError('Wrong edition or mismatched item ID')
        insert(names, key, row['name'])
    return names


def petscout_names(text, table):
    if 'build 1.60.1.69913' not in text or 'ns.' + table + ' = {' not in text:
        raise ValueError('Unexpected PetScout source')
    text = text[text.index('ns.' + table + ' = {'):]
    names = {}
    pairs = re.findall(r'^  \[(\d+)\] = \{ name = ' + STRING, text, re.M)
    if len(pairs) != text.count('name = '):
        raise ValueError('Unparsed PetScout name')
    for key, token in pairs:
        insert(names, key, json.loads(token))
    if not names:
        raise ValueError('Empty PetScout names')
    return names


def compile_supplements(data):
    sources = data / 'supplement-sources'
    manifest = json.loads((sources / 'manifest.json').read_text())
    snapshots = {}
    for entry in manifest:
        raw = (sources / entry['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Source checksum mismatch: ' + entry['file'])
        snapshots[entry['file']] = raw.decode('utf-8')
    with (data / 'ItemSparse.1.60.1.70124.csv').open(encoding='utf-8-sig', newline='') as f:
        base = {int(r['ID']): r['Display_lang'] for r in csv.DictReader(f) if r['Display_lang'].strip()}
    merged = dict(base)
    additions, origins, counts, conflicts = {}, {}, {}, []
    for source, values in [
        ('questiedb-foreverBaseItem.lua', questie_items(snapshots['questiedb-foreverBaseItem.lua'])),
        ('wowhead_forever_gearplanner.txt', gear_items(snapshots['wowhead_forever_gearplanner.txt'])),
    ]:
        counts[source] = {'names': len(values), 'added': 0}
        for key, value in sorted(values.items()):
            if key in merged:
                if merged[key] != value:
                    conflicts.append(dict(id=key, selected=merged[key], alternative=value, source=source))
                continue
            merged[key] = additions[key] = value
            origins[key] = source
            counts[source]['added'] += 1
    currency = {}
    for row in json.loads(snapshots['currencies.json']):
        if row['build'] != '1.60.1.70124':
            raise ValueError('Unexpected currency build')
        insert(currency, row['id'], row['name'])
    report = dict(base_count=len(base), added_count=len(additions), total_count=len(merged),
                  source_counts=counts, conflicts=conflicts, manifest=manifest)
    pets = petscout_names(snapshots['petscout-locations.lua'], 'Locations')
    return {'item': additions, 'currency': currency, 'companion': pets}, origins, report


def render(names):
    lines = ['-- Generated offline by tools/build_supplements.py. See docs/SUPPLEMENT-SOURCES.md.',
             'local _, ns = ...', '-- Load after Resolver.lua; preserve the original Wago pack and metadata.',
             'local supplements = {']
    for kind, entries in sorted(names.items()):
        lines.append('    ' + kind + ' = {')
        lines += ['        [%d] = %s,' % (key, lua_string(value)) for key, value in sorted(entries.items())]
        lines.append('    },')
    lines += ['}', 'for kind, entries in pairs(supplements) do',
              '    ns.Names[kind] = ns.Names[kind] or {}',
              '    local meta = {}',
              '    for key, value in pairs(ns.PackMeta[kind] or {}) do meta[key] = value end',
              '    local added = 0', '    for id, name in pairs(entries) do',
              '        if ns.Names[kind][id] == nil then',
              '            ns.Names[kind][id] = name; added = added + 1',
              '        end', '    end',
              '    meta.count = 0',
              '    for _ in pairs(ns.Names[kind]) do meta.count = meta.count + 1 end',
              '    meta.communityAdded = added',
              '    meta.coverage = "forever-with-community-supplement"',
              '    if kind == "companion" or kind == "uimap" then meta.sourceBuild = "1.60.1.69913" end',
              '    if kind == "currency" then meta.sourceBuild = "1.60.1.70124" end',
              '    ns.PackMeta[kind] = meta', 'end', '']
    return '\n'.join(lines)


def main():
    root = Path(__file__).resolve().parents[1]
    data = root / 'data'
    names, origins, report = compile_supplements(data)
    (root / 'EnglishLinks/SupplementNames_enUS.lua').write_text(render(names))
    (data / 'supplement-report.json').write_text(json.dumps(report, indent=2) + '\n')
    with (data / 'ItemNames.community.csv').open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(['ID', 'Name', 'Source'])
        writer.writerows((key, value, origins[key]) for key, value in sorted(names['item'].items()))
    print('Supplement items:', report['added_count'], 'total:', report['total_count'],
          'currencies:', len(names['currency']), 'conflicts:', len(report['conflicts']))


if __name__ == '__main__':
    main()

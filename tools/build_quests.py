#!/usr/bin/env python3
"""Build offline quest titles from pinned source snapshots; never execute their Lua."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
from build_names import lua_string
from build_packs import name_ok, read_file, lua

STRING = r'("(?:\\.|[^"\\])*")'


def decode_string(token):
    # These pinned sources use JSON-compatible quoted Lua strings.
    # Reject unsupported escape forms instead of silently corrupting a title.
    result = json.loads(token)
    if not name_ok(result):
        raise ValueError('Invalid quest title: ' + repr(result))
    return result


def extract(text, source):
    if source == 'questiedb/foreverQuestDB.lua':
        pattern = r'^\[(\d+)\] = \{' + STRING
    elif source == 'questiedb/foreverBaseQuest.lua':
        pattern = r'^\s*\[(\d+)\]\s*=\s*\{[^\n]*\n\s*\[questKeys.name\]\s*=\s*' + STRING
    elif source == 'EverythingQuests/QuestAvailable_Forever.lua':
        start = text.index('names = {')
        text = text[start:text.index('\n}', start)]
        pattern = r'\[(\d+)\]\s*=\s*' + STRING
    elif source == 'Completao/ForeverNew.lua':
        pattern = r'\{ id = (\d+), name = ' + STRING
    else:
        raise ValueError('Unknown source: ' + source)
    result = {}
    for key, token in re.findall(pattern, text, re.M):
        title = decode_string(token)
        if source == 'Completao/ForeverNew.lua':
            # Its generator decorates chain steps for display, not actual titles.
            title = re.sub(r' \(\d+/\d+\)$', '', title)
        key = int(key)
        if key in result and result[key] != title:
            raise ValueError('Conflicting duplicate ID in ' + source)
        result[key] = title
    if not result:
        raise ValueError('No quest names in ' + source)
    return result


def compile_quests(source_dir, quest_csv):
    rows, quest_hash = read_file(quest_csv)
    ids = {int(row['ID']) for row in rows}
    manifest = json.loads((source_dir / 'manifest.json').read_text())
    data = {}
    for entry in manifest:
        raw = (source_dir / entry['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Source checksum mismatch: ' + entry['file'])
        data[entry['file']] = extract(raw.decode('utf-8'), entry['file'])
    # Forever additions first; preserve the established baseline on conflicts.
    priority = ['questiedb/foreverBaseQuest.lua', 'questiedb/foreverQuestDB.lua',
                'EverythingQuests/QuestAvailable_Forever.lua', 'Completao/ForeverNew.lua']
    names, provenance, conflicts = {}, {}, []
    for source in priority:
        for key, title in sorted(data[source].items()):
            if key in names:
                if names[key] != title:
                    conflicts.append(dict(id=key, selected=names[key], selected_source=provenance[key],
                                          alternative=title, alternative_source=source))
                continue
            names[key], provenance[key] = title, source
    return names, provenance, dict(manifest=manifest, questv2_sha256=quest_hash,
        questv2_count=len(ids), count=len(names), source_counts=dict(Counter(provenance.values())),
        missing_ids=sorted(ids - names.keys()), outside_reference_ids=sorted(names.keys() - ids), conflicts=conflicts)


def render(names, build, report):
    lines = ['-- Generated offline by tools/build_quests.py. See docs/QUEST-SOURCES.md.',
             'local _, ns = ...', 'ns.Names = ns.Names or {}', 'ns.PackMeta = ns.PackMeta or {}',
             'ns.Names.quest = {']
    lines += ['    [%d] = %s,' % (key, lua_string(value)) for key, value in sorted(names.items())]
    lines += ['}', 'ns.PackMeta.quest = ' + lua(dict(build=build, locale='enUS', count=len(names),
        coverage='community-forever-with-inherited-classic', questv2_count=report['questv2_count'])), '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--build', default='1.60.1.70124')
    parser.add_argument('--output', type=Path, default=Path('EnglishLinks/QuestNames_enUS.lua'))
    args = parser.parse_args()
    if not re.fullmatch(r'1\.60\.\d+\.\d+', args.build):
        parser.error('Expected an exact Forever build')
    names, provenance, report = compile_quests(args.data_dir / 'quest-sources',
        args.data_dir / ('QuestV2.' + args.build + '.csv'))
    args.output.write_text(render(names, args.build, report), encoding='utf-8')
    (args.data_dir / 'quest-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    with (args.data_dir / 'QuestNames.community.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['ID', 'Name', 'Source'])
        writer.writerows((key, names[key], provenance[key]) for key in sorted(names))
    print('Quest names:', len(names), '/', report['questv2_count'])
    print('Selected sources:', report['source_counts'])
    print('Conflicts retained in report:', len(report['conflicts']))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Build typed EnglishLinks name packs from one exact Forever build (stdlib only).
No Classic fallback, no guessed cross-table IDs, no evaluation of Lua input.
"""
import argparse
import csv
import hashlib
import io
from pathlib import Path
import re
import tempfile
import os
from build_names import lua_string

# DB2 schema names from wowdev/WoWDBDefs. No row positions are assumed.
DIRECT = {
    'SpellName': ('spell', 'Name_lang'),
    'SkillLine': ('profession', 'DisplayName_lang'),
    'Achievement': ('achievement', 'Title_lang'),
    'CurrencyTypes': ('currency', 'Name_lang'),
    'UiMap': ('uimap', 'Name_lang'),
    'Mount': ('mount', 'Name_lang'),
}
RELATIONAL = {'BattlePetSpecies','Creature','Talent','SkillLineAbility','QuestV2'}
KINDS = {x[0] for x in DIRECT.values()} | {'item','quest','companion','talent'}
CORE = {'SpellName','SkillLine','Achievement'}


def name_ok(name):
    return (bool(name.strip()) and len(name.encode('utf-8')) <= 255
            and not any(ord(c) < 32 or ord(c) == 127 or c == '|' for c in name))


def put(mapping, key, name):
    if not name or not name.strip(): return
    if not name_ok(name): raise ValueError('Invalid name for ID %s: %r' % (key, name))
    if key in mapping and mapping[key] != name: raise ValueError('Conflicting names for ID %s' % key)
    mapping[key] = name


def number(raw, allow_zero=False):
    if not re.fullmatch(r'\d+', str(raw or '')): raise ValueError('Invalid integer ID: %r' % raw)
    n = int(raw)
    if n < (0 if allow_zero else 1) or n > 2147483647: raise ValueError('Out-of-range ID: %s' % n)
    return n


def require(rows, fields, table):
    if not fields <= set(rows[0]): raise ValueError('%s requires columns %s' % (table, ', '.join(sorted(fields))))


def read_file(path):
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not reader.fieldnames or 'ID' not in reader.fieldnames: raise ValueError('%s is not a DB2 CSV with ID' % path.name)
    rows = list(reader)
    if not rows: raise ValueError('%s is empty' % path.name)
    if any(None in row or any(v is None for v in row.values()) for row in rows): raise ValueError('Malformed CSV rows in %s' % path.name)
    ids = [number(row['ID'], True) for row in rows]
    if len(ids) != len(set(ids)): raise ValueError('Duplicate IDs in %s' % path.name)
    rows = [row for row in rows if int(row["ID"]) != 0]
    if not rows: raise ValueError("No usable rows in " + path.name)
    return rows, hashlib.sha256(raw).hexdigest()


def compile_directory(directory, build, allow_partial=False):
    if not re.fullmatch(r'1\.60\.\d+\.\d+', build): raise ValueError('Expected an exact Forever build 1.60.x.x')
    tables, hashes, source_files = {}, {}, {}
    for path in sorted(directory.glob('*.csv')):
        table = path.name.split('.')[0]
        if table not in DIRECT and table not in RELATIONAL: continue
        embedded = re.search(r'(\d+\.\d+\.\d+\.\d+)', path.name[len(table)+1:])
        if embedded and embedded.group(1) != build: raise ValueError('Wrong build in filename: %s' % path.name)
        if table in tables: raise ValueError('Multiple CSVs for %s; keep one exact build' % table)
        tables[table], hashes[table] = read_file(path)
        source_files[table] = path.name
    absent = sorted(CORE - tables.keys())
    if absent and not allow_partial: raise ValueError('Missing required CSVs: ' + ', '.join(absent) + '; use --allow-partial only intentionally')
    names, relations = {}, {}
    for table, (kind, column) in DIRECT.items():
        if table not in tables: continue
        require(tables[table], {'ID',column}, table)
        if table == 'Mount': require(tables[table], {'SourceSpellID'}, table)
        names[kind] = {}
        for row in tables[table]:
            key = row['SourceSpellID'] if table == 'Mount' else row['ID']
            if table == 'Mount' and number(key, True) == 0: continue
            put(names[kind], number(key), row[column])
    if 'BattlePetSpecies' in tables:
        if 'Creature' not in tables: raise ValueError('BattlePetSpecies needs Creature for species names')
        require(tables['BattlePetSpecies'], {'CreatureID'}, 'BattlePetSpecies')
        require(tables['Creature'], {'Name_lang'}, 'Creature')
        creatures = {number(r['ID']):r['Name_lang'] for r in tables['Creature']}
        names['companion'] = {}
        for row in tables['BattlePetSpecies']:
            # Missing creature names remain missing; summon spell names are NOT species names.
            value = creatures.get(number(row['CreatureID'], True), '')
            put(names['companion'], number(row['ID']), value)
    if 'Talent' in tables:
        rows = tables['Talent']; relations['talent'] = {}
        rank_cols = sorted((k for k in rows[0] if re.fullmatch(r'SpellRank_\d+', k)), key=lambda k:int(k.split('_')[-1]))
        if not rank_cols and 'SpellID' not in rows[0]: raise ValueError('Talent requires SpellID or SpellRank_N columns')
        for row in rows:
            value = [number(row[k], True) for k in rank_cols] if rank_cols else number(row['SpellID'], True)
            if value: relations['talent'][number(row['ID'])] = value
    if 'SkillLineAbility' in tables:
        rows = tables['SkillLineAbility']; require(rows, {'SkillLine','Spell'}, 'SkillLineAbility')
        relations['recipe'] = {}; ambiguous = set()
        for row in rows:
            spell, skill = number(row['Spell'], True), number(row['SkillLine'], True)
            if not spell or not skill: continue
            if spell in relations['recipe'] and relations['recipe'][spell] != skill: ambiguous.add(spell)
            relations['recipe'][spell] = skill
        for spell in ambiguous: relations['recipe'].pop(spell, None)
    quest_ids = sorted(number(r['ID']) for r in tables.get('QuestV2', []))
    if not tables: raise ValueError('No supported input files; output not changed')
    return names, relations, quest_ids, {table:{'file':source_files[table],'sha256':hashes[table]} for table in tables}, absent



def lua(value):
    if isinstance(value, str): return lua_string(value)
    if isinstance(value, int): return str(value)
    if isinstance(value, list): return '{' + ','.join(lua(v) for v in value) + '}'
    return '{' + ','.join('['+lua(k)+']='+lua(v) for k,v in sorted(value.items())) + '}'


def render(compiled, build):
    names, relations, quest_ids, sources, absent = compiled
    lines = ['-- Generated from Forever/enUS CSVs by tools/build_packs.py. No Classic fallback.',
             'local _, ns = ...', 'ns.Names = ns.Names or {}', 'ns.PackMeta = ns.PackMeta or {}',
             'ns.PackSources = '+lua(sources)]
    for kind, entries in sorted(names.items()):
        lines += ['ns.Names.'+kind+' = {']
        lines += ['    [%d] = %s,' % (id, lua_string(name)) for id,name in sorted(entries.items())]
        lines += ['}', 'ns.PackMeta.'+kind+' = '+lua({'build':build,'locale':'enUS','count':len(entries)})]
    lines += ['ns.Relations = '+lua(relations),'']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path, required=True)
    p.add_argument('--build', required=True)
    p.add_argument('--allow-partial', action='store_true')
    p.add_argument('--output', type=Path, default=Path('EnglishLinks/Names_enUS.lua'))
    args = p.parse_args()
    try:
        if not args.input_dir.is_dir(): raise ValueError('Input directory does not exist')
        result = compile_directory(args.input_dir, args.build, args.allow_partial)
        content = render(result, args.build)
    except (ValueError,KeyError,TypeError,UnicodeError,OSError) as e: p.exit(1, str(e)+'\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=args.output.parent, delete=False) as f:
        temporary = Path(f.name); f.write(content)
    try: os.replace(temporary,args.output)
    finally: temporary.unlink(missing_ok=True)
    print('Name counts:', {k:len(v) for k,v in result[0].items()})
    print('Quest IDs:',len(result[2]),'; missing core tables:',result[-1])
    print('Wrote',args.output)

if __name__ == '__main__': main()

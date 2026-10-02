#!/usr/bin/env python3
"""Developer test runner. Requires: python -m pip install lupa"""
from pathlib import Path
import argparse
import csv
import hashlib
import subprocess
import sys
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(root / 'tests'), '-p', 'test_*.py'], check=True)
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute((root / 'tests/test_links.lua').read_text(), str(root))
LuaRuntime(unpack_returned_tuples=True).execute((root / "tests/test_typed.lua").read_text(), str(root))
# Load the entire shipped database in the same Lua version as the pure tests.
ns = lua.table()
lua.execute((root / 'EnglishLinks/ItemNames_enUS.lua').read_text(), 'EnglishLinks', ns)
assert ns.ItemNames[6948] == 'Hearthstone'
assert ns.ItemNames[785] == 'Mageroyal'
assert len(list(ns.ItemNames.keys())) == ns.ItemNamesMeta.count
print('Full shipped database loaded in Lua 5.1:', ns.ItemNamesMeta.count, 'names')

assert ns.ItemNamesMeta.build == '1.60.1.70124'
assert ns.ItemNamesMeta.coverage == 'forever'
assert ns.ItemNames[260210] == 'A Bigger Shield'
args = argparse.ArgumentParser()
args.add_argument('--csv', type=Path, help='Verify every shipped ID and name against the original Wago export')
args.add_argument('--data-dir', type=Path, help='Verify all extension packs against original CSVs')
options = args.parse_args()
if options.csv:
    raw = options.csv.read_bytes()
    with options.csv.open(encoding='utf-8-sig', newline='') as f:
        expected = {int(row['ID']): row['Display_lang'] for row in csv.DictReader(f) if row['Display_lang'].strip()}
    actual = dict(ns.ItemNames.items())
    assert actual == expected, 'Shipped database differs from the input CSV'
    assert ns.ItemNamesMeta.sha256 == hashlib.sha256(raw).hexdigest()
    print('All', len(expected), 'IDs/names and source SHA-256 match the original CSV exactly')

# Load and resolve real shipped data; fixture tables are isolated in other runtimes.
real = LuaRuntime(unpack_returned_tuples=True)
real.execute('GetLocale=function() return "ruRU" end; GetBuildInfo=function() return "1.60.1","70124" end')
actual_ns = real.table()
for name in ['ItemNames_enUS','Names_enUS','QuestNames_enUS','LinkText','Resolver','SupplementNames_enUS']:
    real.execute((root / ('EnglishLinks/' + name + '.lua')).read_text(), 'EnglishLinks', actual_ns)
actual_ns.InitDB(real.table())
for payload, expected in [
    ('item:6948::::::::::::','Hearthstone'),
    ('item:251485::::::::::::',"Edward's Knife"),
    ('item:286556::::::::::::','Winds of Tanaris'),
    ('currency:3402:0',"Merchant's Favor"),
    ('nonbattlepet:5005','Musical Gustjumper'),
    ('mount:458:0','Brown Horse'),
    ('worldmap:1429:1234:5678','Map Pin Location'),
    ('spell:133','Fireball'),
    ('quest:92485:2','A Student of Nature'),
    ('quest:92466:2','Call of Earth'),
    ('quest:7:2','Kobold Camp Cleanup'),
    ('enchant:2329','Elixir of Minor Strength'),
    ('trade:Player-1-ABC:2259:171','Alchemy'),
    ('trade:2259:1:300:GUID:bits','Alchemy'),
    ('achievement:49:Player-1-ABC:1:0:0:0:0:0:0:0','Alterac Valley victories'),
]:
    assert actual_ns.Resolve(payload, 'Русское', None) == expected, payload
assert actual_ns.Resolve('quest:2147483647:60', 'Задание', None) is None
assert actual_ns.Resolve('item:6948:0:0:0:0:0:-10:123', 'Суффикс', None) is None
assert actual_ns.Lookup('spell', 2330, None) is None  # Not present in this Forever export.
print('Real shipped link smoke checks passed')
# Reproduce the reported recipe inputs with the actual shipped names. These
# checks cover our output only; accepting/rendering it requires a live client.
for recipe_id, localized, english in [
    (3816, 'Кожевничество: Обработанная легкая шкура', 'Cured Light Hide'),
    (1229517, 'Снятие шкур: Лагерный стул', 'Camp Chair'),
]:
    original = f'|cffffd000|Henchant:{recipe_id}|h[{localized}]|h|r'
    expected = f'|cffffd000|Henchant:{recipe_id}|h[{english}]|h|r'
    before, after = 'До ', ' после |cffffffff|Hitem:6948|h[Hearthstone]|h|r'
    message = before + original + after
    result, cursor, count = actual_ns.TranslateAll(message, actual_ns.Resolve, len((before + original).encode()))
    assert result == before + expected + after
    assert cursor == len((before + expected).encode()) and count == 1
    assert actual_ns.TranslateAll(result, actual_ns.Resolve, cursor) == (result, cursor, 0)
    actual_ns.DB.types.enchant = False
    assert actual_ns.TranslateAll(original, actual_ns.Resolve)[0] == original
    actual_ns.DB.types.enchant = True
    actual_ns.DB.typedOverrides.spell[recipe_id] = 'Custom Recipe'
    assert actual_ns.Resolve(f'enchant:{recipe_id}', localized, None) == 'Custom Recipe'
    actual_ns.DB.typedOverrides.spell[recipe_id] = None
print('Recipe label regressions passed (live confirmation recorded separately)')
if options.data_dir:
    sys.path.insert(0, str(root / 'tools'))
    import build_packs
    compiled = build_packs.compile_directory(options.data_dir, actual_ns.ItemNamesMeta.build)
    assert (root / 'EnglishLinks/Names_enUS.lua').read_text() == build_packs.render(compiled, actual_ns.ItemNamesMeta.build)
    for kind, mapping in compiled[0].items():
        assert dict(actual_ns.Names[kind].items()) == mapping
        assert actual_ns.PackMeta[kind].count == len(mapping)
    assert actual_ns.QuestIDs is None
    assert dict(actual_ns.Relations.recipe.items()) == compiled[1]['recipe']
    import build_quests
    titles, provenance, report = build_quests.compile_quests(options.data_dir / 'quest-sources', options.data_dir / 'QuestV2.1.60.1.70124.csv')
    assert len(titles) == 5000
    assert report['conflicts'] == []
    assert dict(actual_ns.Names.quest.items()) == titles
    assert (root / 'EnglishLinks/QuestNames_enUS.lua').read_text() == build_quests.render(titles, actual_ns.ItemNamesMeta.build, report)
    print('All typed names, quest titles, recipe relations and source hashes match their inputs')
    import build_supplements
    extra, origins, report = build_supplements.compile_supplements(options.data_dir)
    assert report['total_count'] == 24037
    # The newer supplemental planner disagrees with older fallback names.
    # Supplements must not overwrite those; the primary Wowhead overlay does.
    assert {row['id'] for row in report['conflicts']} == {254696, 263411, 263412, 274749}
    for row in report['conflicts']:
        assert actual_ns.Names.item[row['id']] == row['selected']
    assert actual_ns.PackMeta.item.count == 24037
    assert actual_ns.ItemNamesMeta.count == 19224  # Original Wago metadata stays intact.
    assert actual_ns.PackMeta.currency.count == 5
    assert (root / 'EnglishLinks/SupplementNames_enUS.lua').read_text() == build_supplements.render(extra)
    assert dict(actual_ns.Names.item.items()) == dict(ns.ItemNames.items()) | extra['item']
    assert dict(actual_ns.Names.currency.items()) == extra['currency']
    assert dict(actual_ns.Names.companion.items()) == extra['companion']
    assert actual_ns.Names.uimap is None
    assert len(extra['companion']) == 112
    real.execute('C_PetJournal=setmetatable({}, {__index=function() error("Unexpected pet API access") end})')
    assert actual_ns.Resolve('nonbattlepet:39', 'Механическая белка', None) == 'Mechanical Squirrel'
    assert actual_ns.Resolve('battlepet:39:1:2:100:10:10:BattlePet-0', 'Механическая белка', None) is None
    assert actual_ns.Resolve('battlepet:39:1:2:100:10:10:BattlePet-0', 'Моя Белочка', None) is None
    actual_ns.DB.typedOverrides.item[251485] = 'Manual name'
    assert actual_ns.Resolve('item:251485', 'Предмет', None) == 'Manual name'
    actual_ns.DB.types.mount = False
    assert actual_ns.Resolve('mount:458:0', 'Лошадь', None) is None
    print('Community names, source hashes, priority and mount/currency links verified')

#!/usr/bin/env python3
"""Developer test runner. Requires: python -m pip install lupa"""
from pathlib import Path
import subprocess
import sys
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(root / 'tests'), '-p', 'test_*.py'], check=True)
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute((root / 'tests/test_links.lua').read_text(), str(root))
LuaRuntime(unpack_returned_tuples=True).execute((root / "tests/test_typed.lua").read_text(), str(root))
# Load and resolve real shipped data; fixture tables are isolated in other runtimes.
real = LuaRuntime(unpack_returned_tuples=True)
real.execute('GetLocale=function() return "ruRU" end; GetBuildInfo=function() return "1.60.1","70124" end')
actual_ns = real.table()
for name in ['NameData', 'LinkText', 'Resolver']:
    real.execute((root / 'EnglishLinks' / (name + '.lua')).read_text(), 'EnglishLinks', actual_ns)
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
print('Prepared addon link smoke checks passed')
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
real.execute('C_PetJournal=setmetatable({}, {__index=function() error("Unexpected pet API access") end})')
assert actual_ns.Resolve('nonbattlepet:39', 'Механическая белка', None) == 'Mechanical Squirrel'
assert actual_ns.Resolve('battlepet:39:1:2:100:10:10:BattlePet-0', 'Моя Белочка', None) is None
actual_ns.DB.typedOverrides.item[251485] = 'Manual name'
assert actual_ns.Resolve('item:251485', 'Предмет', None) == 'Manual name'
actual_ns.DB.types.mount = False
assert actual_ns.Resolve('mount:458:0', 'Лошадь', None) is None
print('Prepared addon pet, override and type switch regressions passed')

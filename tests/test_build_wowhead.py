import csv
import json
import hashlib
from pathlib import Path
import sys
import unittest
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_wowhead as b


class Wowhead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names, cls.bonuses, cls.manifest = b.compile_snapshot(ROOT / 'data/wowhead-sources')

    def runtime(self):
        runtime = LuaRuntime(unpack_returned_tuples=True)
        ns = runtime.table()
        for filename in (ROOT / 'EnglishLinks/EnglishLinks.toc').read_text().splitlines():
            if filename.endswith('.lua') and filename != 'EnglishLinks.lua':
                runtime.execute((ROOT / 'EnglishLinks' / filename).read_text(), 'EnglishLinks', ns)
        ns.InitDB(runtime.table())
        return runtime, ns

    def test_reproducible_authoritative_overlay(self):
        self.assertEqual((ROOT / 'EnglishLinks/WowheadNames_enUS.lua').read_text(), b.render(self.names, self.bonuses, self.manifest))
        runtime, ns = self.runtime()
        report = json.loads((ROOT / 'data/wowhead-report.json').read_text())
        for kind, rows in self.names.items():
            final = dict(ns.Names[kind].items())
            self.assertTrue(rows.items() <= final.items(), kind)
            self.assertEqual(len(final), report['categories'][kind]['total'])
            self.assertEqual(ns.PackMeta[kind].count, len(final))
            self.assertEqual(ns.PackMeta[kind].primaryCount, len(rows))
        self.assertEqual(ns.Resolve('quest:5641', 'Русское'), 'Chastise')
        self.assertEqual(ns.Resolve('quest:5644', 'Русское'), 'Dark Sacrifice')
        self.assertEqual(ns.Names.quest[2358], 'Horns of Nez\'ra')
        ns.DB.typedOverrides.quest[5641] = 'Manual title'
        self.assertEqual(ns.Resolve('quest:5641', 'Русское'), 'Manual title')
        with (ROOT / 'data/QuestV2.1.60.1.70124.csv').open() as f:
            reference = {int(r['ID']) for r in csv.DictReader(f)}
        outside = self.names['quest'].keys() - reference
        self.assertEqual(len(outside), 751)
        self.assertTrue(all(ns.Names.quest[i] == self.names['quest'][i] for i in outside))
        self.assertEqual(ns.Names.uimap, None)

    def test_bonuses_preserve_variant_and_payload(self):
        _, ns = self.runtime()
        self.assertEqual(self.bonuses[12722], 'of the Bear')
        proof = json.loads((ROOT / 'data/wowhead-sources/bonus-example.json').read_text())
        self.assertEqual(hashlib.sha256(proof['raw_response'].encode()).hexdigest(), proof['sha256'])
        self.assertIn("Commander's Armor of the Bear</b>", json.loads(proof['raw_response'])['tooltip'])
        base = 'item:10378:0:0:0:0:0:0:0:60:0:0:0:'
        cases = [
            ('1:12722', "Commander's Armor of the Bear"),
            ('2:12722:11036', "Commander's Armor of the Bear"),
            ('0', "Commander's Armor"),
            ('1:9999999', None), ('2:12722', None),
            ('2:12722:12718', None), ('-1', None), ('1.5', None),
            ('x', None), ('1:x', None), ('65:' + ':'.join(['12722']*65), None),
        ]
        for tail, expected in cases:
            payload = base + tail
            original = '|cff00ff00|H' + payload + '|h[Броня со случайным окончанием]|h|r'
            wanted = original if expected is None else '|cff00ff00|H' + payload + '|h[' + expected + ']|h|r'
            result, cursor, count = ns.TranslateAll(original, ns.Resolve, len(original.encode()))
            self.assertEqual(result, wanted, tail)
            self.assertEqual(cursor, len(wanted.encode()))
            self.assertEqual(count, int(expected is not None))
        for legacy in ('-10', '10', 'garbage'):
            payload = base.replace(':0:0:60:', ':' + legacy + ':0:60:') + '1:12722'
            self.assertIsNone(ns.Resolve(payload, 'Старый суффикс'))
        ns.DB.types.item = False
        self.assertIsNone(ns.Resolve(base + '1:12722', 'Русское'))

    def test_map_pin_icon_coordinates_cursor_and_switch(self):
        _, ns = self.runtime()
        atlas = '|A:Waypoint-MapPin-ChatIcon:13:13:0:0|a '
        payload = 'worldmap:999999:1234:5678'
        for icon in ('', atlas):
            old = '|cffffff00|H' + payload + '|h[' + icon + 'Координаты точки на карте]|h|r'
            new = '|cffffff00|H' + payload + '|h[' + icon + 'Map Pin Location]|h|r'
            msg = 'До ' + old + ' после'
            expected = 'До ' + new + ' после'
            result, cursor, count = ns.TranslateAll(msg, ns.Resolve, len(('До ' + old).encode()))
            self.assertEqual(result, expected)
            self.assertEqual(cursor, len(('До ' + new).encode()))
            self.assertEqual(count, 1)
            self.assertEqual(ns.TranslateAll(result, ns.Resolve, cursor), (result, cursor, 0))
            icon_cursor = len(('До |cffffff00|H' + payload + '|h[').encode()) + 2
            self.assertEqual(ns.TranslateAll(msg, ns.Resolve, icon_cursor)[1], icon_cursor if icon else len(('До |cffffff00|H' + payload + '|h[Map Pin Location').encode()))
        decorated = '|H' + payload + '|h[|Tcustom:13|tМетка]|h'
        self.assertEqual(ns.TranslateAll(decorated, ns.Resolve)[0], decorated)
        ns.DB.types.worldmap = False
        self.assertEqual(ns.TranslateAll(msg, ns.Resolve)[0], msg)

    def test_data_literals_never_execute(self):
        self.assertEqual(b.decode('{id: 5, name: "x,]", values: [1,],}'), {'id':5, 'name':'x,]', 'values':[1]})
        for text in ('{id: doSomething()}', '{id:1,id:2}', '{"name":"a","name":"b"}'):
            with self.assertRaises(ValueError):
                b.decode(text)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            b.list_rows('var listviewitems = []; _truncated: 1', 'items')


if __name__ == '__main__':
    unittest.main()

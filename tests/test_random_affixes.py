import json
from pathlib import Path
import sys
import unittest
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_random_affixes as b


class RandomAffixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names, cls.manifest = b.compile_snapshot(ROOT / 'data/random-affix-sources')

    def runtime(self):
        runtime = LuaRuntime(unpack_returned_tuples=True)
        ns = runtime.table()
        for name in (ROOT / 'EnglishLinks/EnglishLinks.toc').read_text().splitlines():
            if name.endswith('.lua') and name != 'EnglishLinks.lua':
                runtime.execute((ROOT / 'EnglishLinks' / name).read_text(), 'EnglishLinks', ns)
        ns.InitDB(runtime.table())
        return ns

    def test_every_shipped_signed_id_and_reproducibility(self):
        ns = self.runtime()
        self.assertEqual(len(self.names), 2039)
        self.assertEqual(sum(i < 0 for i in self.names), 27)
        self.assertEqual(dict(ns.ItemRandomAffixes.items()), self.names)
        self.assertEqual((ROOT / 'EnglishLinks/RandomAffixes_enUS.lua').read_text(),
                         b.render(self.names, self.manifest))
        for rid, suffix in self.names.items():
            self.assertEqual(ns.Resolve(f'item:10378:0:0:0:0:0:{rid}:123', 'Предмет'),
                             "Commander's Armor " + suffix, rid)
        self.assertEqual(ns.Resolve('item:6614:0:0:0:0:0:763:123', 'Плащ'),
                         "Sage's Cloak of the Owl")
        self.assertNotIn(-7, self.names)  # A generic tooltip guide is not a Forever mapping.

    def test_payload_cursor_duplicates_conflicts_and_unknown_ids(self):
        ns = self.runtime()
        def payload(rand, bonuses='0'):
            return f'item:10378:0:0:0:0:0:{rand}:123:60:0:0:0:{bonuses}'
        cases = [
            ('1215', '0', "Commander's Armor of the Bear"),
            ('-68', '0', "Commander's Armor of the Bear"),
            ('-9', '0', "Commander's Armor of the Owl"),
            ('1215', '1:12722', "Commander's Armor of the Bear"),
            ('-68', '2:12722:11036', "Commander's Armor of the Bear"),
            ('1215', '1:11036', "Commander's Armor of the Bear"),
            ('-9', '1:12722', None), ('-7', '1:12722', None),
            ('999999', '0', None), ('-999999', '0', None),
            ('1215', '1:999999', None), ('1215', '2:12722', None),
            ('12722', '0', None),  # A bonus ID must not be treated as a rand ID.
            ('', '0', "Commander's Armor"), ('0', '0', "Commander's Armor"),
            ('0', '1:12722', "Commander's Armor of the Bear"),
        ]
        for malformed in ('x', '1.5', '1e3', '+1215', '--68', ' 1215', '2147483648'):
            cases.append((malformed, '0', None))
        for rand, bonuses, name in cases:
            link = '|cff00ff00|H' + payload(rand, bonuses) + '|h[Русское название]|h|r'
            wanted = link if name is None else link.replace('Русское название', name)
            old, expected = 'До ' + link + ' после', 'До ' + wanted + ' после'
            cursor = len(('До ' + link).encode())
            result, mapped, count = ns.TranslateAll(old, ns.Resolve, cursor)
            self.assertEqual(result, expected, (rand, bonuses))
            self.assertEqual(mapped, len(('До ' + wanted).encode()))
            self.assertEqual(count, int(name is not None))
            self.assertEqual(ns.TranslateAll(result, ns.Resolve, mapped), (result, mapped, 0))
        ns.DB.typedOverrides.item[10378] = 'Custom Armor'
        self.assertEqual(ns.Resolve(payload('1215'), 'Предмет'), 'Custom Armor of the Bear')
        ns.DB.types.item = False
        self.assertIsNone(ns.Resolve(payload('1215'), 'Предмет'))

    def test_parser_rejects_duplicate_unsafe_and_mismatched_ids(self):
        def parse(rows):
            return b.parse('WH.setPageData(' + json.dumps(b.TABLE) + ',' + rows + ');')
        self.assertEqual(parse('{"-9":{"id":-9,"name":"of the Owl"}}'), {-9: 'of the Owl'})
        for rows in [
            '{}', '{"0":{"id":0,"name":"Empty"}}',
            '{"9":{"id":-9,"name":"Wrong sign"}}',
            '{"-9":{"id":-9,"name":"A"},"-9":{"id":-9,"name":"B"}}',
            '{"9":{"id":9,"name":"|Hunsafe"}}',
            '{"9":{"id":9,"name":""}}',
        ]:
            with self.assertRaises(ValueError):
                parse(rows)


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import sys
import unittest

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import name_data


class PreviewLinks(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        for file in ('NameData', 'LinkText', 'Resolver'):
            self.lua.execute((ROOT / 'EnglishLinks' / (file + '.lua')).read_text(), 'EnglishLinks', self.ns)
        self.ns.InitDB(self.lua.table())

    def test_bag_crafting_output_and_wardrobe_preserve_payload_and_color(self):
        # IDs, level/spec and bonus 3524 come from the user's screenshots.
        # These are normalized item payloads, not a byte-exact OCR transcript.
        cases = [
            ('item:1251::::::::15:1482:::::::::', 'Q1', 'Льняные бинты', 'Linen Bandage'),
            ('item:1251::::::::15:1482:::1:3524::::::', 'Q1', 'Льняные бинты', 'Linen Bandage'),
            ('item:271097::::::::15:1482:::1:3524::::::', 'Q3', 'Пелерина неприкаянного духа', 'Spiritwraith Drape'),
        ]
        for payload, quality, localized, english in cases:
            with self.subTest(payload=payload):
                link = f'|cnI{quality}:|H{payload}|h[{localized}]|h|r'
                message = 'До ' + link + ' после'
                expected = message.replace(localized, english)
                result, cursor, count = self.ns.TranslateAll(message, self.ns.Resolve, len(('До ' + link).encode()))
                self.assertEqual(result, expected)
                self.assertEqual(cursor, len(('До ' + link.replace(localized, english)).encode()))
                self.assertEqual(count, 1)
                self.assertEqual(self.ns.TranslateAll(result, self.ns.Resolve, cursor), (result, cursor, 0))

    def test_preview_bonus_does_not_hide_real_suffixes_or_unknown_bonuses(self):
        base = 'item:10378:0:0:0:0:0:{rand}:0:15:1482:0:0:'
        for rand, bonuses, expected in [
            (0, '1:3524', "Commander's Armor"),
            (0, '2:3524:12722', "Commander's Armor of the Bear"),
            (0, '2:12722:3524', "Commander's Armor of the Bear"),
            (-9, '1:3524', "Commander's Armor of the Owl"),
            (-9, '2:3524:12722', None),
            (0, '2:3524:9999999', None),
            (0, '2:3524', None),
        ]:
            with self.subTest(rand=rand, bonuses=bonuses):
                self.assertEqual(self.ns.Resolve(base.format(rand=rand) + bonuses, 'Исходное'), expected)
        self.ns.DB.types.item = False
        self.assertIsNone(self.ns.Resolve('item:1251::::::::15:1482:::1:3524', 'Льняные бинты'))

    def test_incremental_refresh_retains_client_observed_bonus(self):
        current = name_data.from_namespace(self.ns)
        updated, changes = name_data.merge(current, {'bonuses': {12722: 'of the Bear'}}, [])
        self.assertEqual(updated['bonuses'][3524], '')
        self.assertEqual(changes, [])


if __name__ == '__main__':
    unittest.main()

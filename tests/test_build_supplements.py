import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_supplements as b


class Supplements(unittest.TestCase):
    def gear(self, row, key='123'):
        return 'WH.setPageData("wow.gearPlanner.classicplus.item", {' + json.dumps(key) + ':' + json.dumps(row) + ',\n});\nnot_executed()'

    def test_edition_and_id_guards(self):
        row = dict(id=123, name='A "quoted" name', versionNum=16001)
        self.assertEqual(b.gear_items(self.gear(row)), {123:row['name']})
        with self.assertRaises(ValueError): b.gear_items(self.gear(row, '124'))
        row['versionNum'] = 11509
        with self.assertRaises(ValueError): b.gear_items(self.gear(row))

    def test_questie_comment_and_explicit_must_agree(self):
        text = '        [123] = { -- Horse : https://wowhead.com/forever/item=123/horse\n            [itemKeys.name] = "Horse",\n'
        self.assertEqual(b.questie_items(text), {123:'Horse'})
        with self.assertRaises(ValueError): b.questie_items(text.replace('= "Horse"', '= "Other"'))
        with self.assertRaises(ValueError): b.questie_items(text.replace('item=123/', 'item=124/'))
        with self.assertRaises(ValueError): b.questie_items('[itemKeys.name] = function() end')

    def test_untrusted_markup(self):
        with self.assertRaises(ValueError):
            b.gear_items(self.gear(dict(id=123, name='|Hspell:1|h[X]|h', versionNum=16001)))


if __name__ == '__main__': unittest.main()

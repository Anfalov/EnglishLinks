import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_names', ROOT / 'tools/build_names.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class BuildNamesTest(unittest.TestCase):
    def test_wago_csv_bom_quotes_and_empty_names(self):
        raw = '\ufeffID,Display_lang,Other\n6948,Hearthstone,0\n42,"A, B",0\n44,,0\n'.encode('utf-8')
        self.assertEqual(builder.collect(raw, 'csv'), {6948:'Hearthstone',42:'A, B'})

    def test_lua_escaping(self):
        self.assertEqual(builder.lua_string('a"b\\c\n7'), '"a\\"b\\\\c\\0107"')

    def test_duplicate_conflict(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            builder.collect(b'ID,Display_lang\n1,One\n1,Two\n', 'csv')

    def test_reject_html_wrong_columns_empty_and_unsafe(self):
        for raw in [b'<html>blocked</html>', b'id,name\n1,Name', b'ID,Display_lang\n',
                    b'ID,Display_lang\n1,|Hbad', b'ID,Display_lang\n-1,Name']:
            with self.subTest(raw=raw), self.assertRaises(ValueError): builder.collect(raw, 'csv')

    def test_nexus_entities(self):
        self.assertEqual(builder.collect(b'[{"itemId":1,"name":"Hero&apos;s Sword"}]','json'), {1:"Hero's Sword"})

    def test_deterministic_sorted_render(self):
        out = builder.render({9:'Nine',1:'One'},'test','source','classic-fallback','hash')
        self.assertLess(out.index('[1]'),out.index('[9]'))
        self.assertIn('locale = "enUS"',out)

if __name__ == '__main__': unittest.main()

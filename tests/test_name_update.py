import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import name_data as data
import update_names as update
import package_release as package


def baseline():
    return dict(names={'item': {1: 'Current', 2: 'Retained'}}, bonuses={10: ''},
                random_affixes={-9: 'of the Owl'})


class IncrementalUpdate(unittest.TestCase):
    def test_primary_replaces_supplement_only_fills_and_nothing_is_deleted(self):
        original = baseline()
        primary = dict(names={'item': {1: 'Wowhead', 3: 'New primary'}}, random_affixes={-10: 'of the Bear'})
        supplemental = [('other', dict(names={'item': {1: 'Wrong', 2: 'Wrong', 3: 'Wrong', 4: 'New fallback'}}))]
        merged, changes = data.merge(original, primary, supplemental)
        self.assertEqual(merged['names']['item'], {1: 'Wowhead', 2: 'Retained', 3: 'New primary', 4: 'New fallback'})
        self.assertEqual(merged['random_affixes'], {-9: 'of the Owl', -10: 'of the Bear'})
        self.assertEqual(original, baseline())
        again, repeated = data.merge(merged, primary, supplemental)
        self.assertEqual(again, merged)
        self.assertEqual(repeated, [])
        self.assertEqual(len(changes), 4)

    def test_missing_sources_are_a_no_op_and_unsafe_names_fail(self):
        self.assertEqual(data.merge(baseline(), {}, []), (baseline(), []))
        with self.assertRaises(ValueError):
            data.merge(baseline(), {'names': {'item': {1: '|Hunsafe'}}}, [])

    def test_apply_records_previous_base_and_repeated_check_changes_no_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'EnglishLinks/NameData.lua'
            path.parent.mkdir()
            original = data.render(baseline())
            path.write_text(original)
            registry = root / 'data/source-registry.json'
            registry.parent.mkdir()
            registry.write_text('{}')
            args = ['update_names.py', '--root', str(root), '--output', str(root / 'output'),
                    '--apply', '--run-id', 'test']
            primary = update.named('item', {1: 'New primary'})
            with patch.object(sys, 'argv', args), patch.object(update, 'wowhead', return_value=primary), \
                    patch.object(update, 'other_sources', return_value=[]):
                update.main()
                saved = path.read_bytes(), registry.read_bytes()
                update.main()
            self.assertEqual((path.read_bytes(), registry.read_bytes()), saved)
            self.assertEqual((root / 'data/auto-updates/test/before.lua').read_text(), original)
            self.assertFalse(json.loads((root / 'output/report.json').read_text())['changed'])

    def test_conflicting_primary_responses_keep_existing_name(self):
        primary, conflicts = update.combine_primary([
            update.named('item', {1: 'First', 3: 'Good'}),
            update.named('item', {1: 'Different'}),
            update.named('item', {1: 'First'})])
        self.assertEqual(conflicts, [('names', 'item', 1)])
        self.assertEqual(data.merge(baseline(), primary, [])[0]['names']['item'],
                         {1: 'Current', 2: 'Retained', 3: 'Good'})

    def test_capped_wowhead_lists_split_and_a_failed_source_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory, entries in [
                ('wowhead-sources', [dict(parser='list', category='items', kind='item', lo=0, hi=3,
                                        url='https://www.wowhead.com/forever/items?filter=151:151;2:4;0:3')]),
                ('random-affix-sources', [dict(parser='randomEnchant', url='https://nether.wowhead.com/forever/data/gear-planner')])]:
                path = root / 'data' / directory
                path.mkdir(parents=True)
                (path / 'manifest.json').write_text(json.dumps({'files': entries}))
            class Fake:
                def get(self, url, *args):
                    if 'gear-planner' in url:
                        raise OSError('Unavailable')
                    low, high = map(int, url.rsplit(';', 1)[1].split(':'))
                    view = dict(id='items', data=[dict(id=i, name=f'Item {i}') for i in range(max(low, 1), high + 1)])
                    if high - low > 1:
                        view['_truncated'] = True
                    return ('<script type="application/json" id="data.page.listPage.listviews">' + json.dumps([view]) + '</script>').encode()
            outcomes = []
            parsed = update.wowhead(Fake(), {'names': {}}, root, outcomes)
            self.assertEqual(parsed['names']['item'], {1: 'Item 1', 2: 'Item 2', 3: 'Item 3'})
            self.assertTrue(any(s['status'] == 'skipped' and s['reason'] == 'Unavailable' for s in outcomes))



class PreparedAddon(unittest.TestCase):
    def test_dictionary_round_trip_and_actual_toc_loading(self):
        path = ROOT / 'EnglishLinks/NameData.lua'
        current = data.load(path)
        self.assertEqual(path.read_text(), data.render(current))
        runtime = LuaRuntime(unpack_returned_tuples=True)
        ns = runtime.table()
        for name in (ROOT / 'EnglishLinks/EnglishLinks.toc').read_text().splitlines():
            if name.endswith('.lua') and name != 'EnglishLinks.lua':
                runtime.execute((ROOT / 'EnglishLinks' / name).read_text(), 'EnglishLinks', ns)
        ns.InitDB(runtime.table())
        self.assertEqual(data.from_namespace(ns), current)
        for kind, rows in current['names'].items():
            self.assertEqual(ns.PackMeta[kind].count, len(rows))
        for rid, suffix in current['random_affixes'].items():
            self.assertEqual(ns.Resolve(f'item:10378:0:0:0:0:0:{rid}:123', 'Исходное'),
                             current['names']['item'][10378] + ' ' + suffix)
        self.assertEqual(ns.Resolve('enchant:1229517', 'Исходное'), current['names']['spell'][1229517])

    def test_package_contains_only_installable_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            import shutil, zipfile
            shutil.copytree(ROOT / 'EnglishLinks', root / 'EnglishLinks')
            (root / 'EnglishLinks/unrelated.lua').write_text('must not ship')
            with patch.object(package, 'ROOT', root):
                package.main()
            archives = list((root / 'dist').iterdir())
            self.assertEqual(len(archives), 1)
            with zipfile.ZipFile(archives[0]) as archive:
                names = set(archive.namelist())
            self.assertIn('EnglishLinks/NameData.lua', names)
            self.assertIn('EnglishLinks/LICENSE', names)
            self.assertNotIn('EnglishLinks/unrelated.lua', names)
            self.assertFalse(any('README' in name or 'CurseForge' in name or name.startswith('data/') for name in names))


if __name__ == '__main__':
    unittest.main()

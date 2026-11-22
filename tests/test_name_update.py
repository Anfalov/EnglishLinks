import json
import io
from email.message import Message
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
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


class FetchDiagnostics(unittest.TestCase):
    def test_wowhead_refusal_stops_further_requests_to_that_host(self):
        url = 'https://www.wowhead.com/forever/quests'
        error = urllib.error.HTTPError(url, 403, 'Forbidden', Message(), io.BytesIO(b'Blocked'))
        with tempfile.TemporaryDirectory() as temp:
            fetcher = update.Fetcher(Path(temp))
            with patch.object(update.urllib.request, 'urlopen', side_effect=error) as request:
                with self.assertRaises(urllib.error.HTTPError):
                    fetcher.get(url, 'wowhead-forever')
                with self.assertRaises(update.SourceBlockedError):
                    fetcher.get(url + '?filter=test', 'wowhead-forever')
                self.assertEqual(request.call_count, 1)
            self.assertTrue(fetcher.records[1]['request_skipped'])
            self.assertNotIn('nether.wowhead.com', fetcher.blocked_hosts)

    def test_forbidden_response_is_archived_but_still_fails(self):
        headers = Message()
        headers['Content-Type'] = 'text/html'
        headers['X-Cache'] = 'Error from cloudfront'
        headers['Set-Cookie'] = 'private=value'
        url = 'https://www.wowhead.com/forever/quests'
        error = urllib.error.HTTPError(url, 403, 'Forbidden', headers,
                                       io.BytesIO(b'<html>Request blocked</html>'))
        with tempfile.TemporaryDirectory() as temp:
            fetcher = update.Fetcher(Path(temp))
            with patch.object(update.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    fetcher.get(url, 'wowhead-forever')
            self.assertIs(raised.exception, error)
            record, = fetcher.records
            self.assertEqual(record['status'], 403)
            self.assertEqual(record['final_url'], url)
            self.assertIn('failed_at', record)
            self.assertFalse(record['body_truncated'])
            self.assertEqual(record['error_body_preview'], '<html>Request blocked</html>')
            self.assertEqual(record['response_headers'], {
                'Content-Type': 'text/html', 'X-Cache': 'Error from cloudfront'})
            self.assertEqual((Path(temp) / record['archive_member']).read_bytes(),
                             b'<html>Request blocked</html>')

    def test_error_response_body_is_bounded(self):
        error = urllib.error.HTTPError('https://example.com', 503, 'Unavailable',
                                       Message(), io.BytesIO(b'x' * (128 * 1024)))
        with tempfile.TemporaryDirectory() as temp:
            fetcher = update.Fetcher(Path(temp))
            with patch.object(update.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(urllib.error.HTTPError):
                    fetcher.get(error.url, 'test')
            record, = fetcher.records
            self.assertTrue(record['body_truncated'])
            self.assertEqual(record['size_bytes'], 64 * 1024)
            self.assertEqual(len(record['error_body_preview']), 4096)


class IncrementalUpdate(unittest.TestCase):
    def test_quest_tooltips_restore_primary_priority_without_deletions(self):
        current = update.named('quest', {7: 'Old', 8: 'Retained', 9: 'Listed before'})
        primary = update.named('quest', {9: 'Fresh list title'})
        additional = [('community', update.named('quest', {7: 'Wrong', 10: 'Fallback title'}))]
        requested = []
        class Fake:
            def get(self, url, source):
                identifier = int(url.split('/')[-1].split('?')[0])
                requested.append(identifier)
                if identifier == 8:
                    return b'{"error": "Not found"}'
                return json.dumps({'name': {7: 'Wowhead renamed', 10: 'Wowhead new'}[identifier]}).encode()
        outcomes = []
        primary = update.quest_tooltips(Fake(), current, primary, additional, outcomes, interval=0)
        merged, changes = data.merge(current, primary, additional)
        self.assertEqual(merged['names']['quest'], {
            7: 'Wowhead renamed', 8: 'Retained', 9: 'Fresh list title', 10: 'Wowhead new'})
        self.assertCountEqual(requested, [7, 8, 10])
        self.assertTrue(all(change['source'] == 'wowhead' for change in changes))
        self.assertEqual(outcomes[-1]['failed'], 1)

    def test_quest_tooltips_stop_after_access_or_rate_limit_refusal(self):
        for status in (403, 429):
            current = update.named('quest', {i: f'Existing {i}' for i in range(1, 30)})
            class Fake:
                def get(self, url, source):
                    raise urllib.error.HTTPError(url, status, 'Refused', Message(), None)
            outcomes = []
            primary = update.quest_tooltips(Fake(), current, update.empty(), [], outcomes, interval=0)
            self.assertEqual(data.merge(current, primary, [])[0], current)
            self.assertLessEqual(outcomes[-1]['requested'], 2)
            self.assertGreater(outcomes[-1]['not_requested'], 0)

    def test_quest_tooltip_invalid_names_do_not_replace_existing_data(self):
        current = update.named('quest', {7: 'Good'})
        for response in [b'{}', b'{"name":"|Hquest:8"}', b'<html>Challenge</html>']:
            class Fake:
                def get(self, *args):
                    return response
            primary = update.quest_tooltips(Fake(), current, update.empty(), [], [], interval=0)
            self.assertEqual(data.merge(current, primary, [])[0], current)

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
                    patch.object(update, 'other_sources', return_value=[]), patch.object(update.quest_sitemap, 'discover', return_value=set()):
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

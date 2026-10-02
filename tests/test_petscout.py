import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import update_names as update
from data_format import lua_string


def archive(build='1.60.1.70170', name='New Pet'):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zipped:
        zipped.writestr('PetScoutForever/data/locations.lua',
                        f'-- build {build}\nns.Locations = {{\n  [5005] = {{ name = "{name}" }},\n}}\n')
    return output.getvalue()


class PetScout(unittest.TestCase):
    def run_source(self, pages):
        pinned = archive(name='Pinned Pet')
        calls, outcomes = [], []
        url = 'https://edge.forgecdn.net/files/8940/612/PetScoutForever-v0.1.1-forever.zip'
        class Fetcher:
            def get(self, target, *args):
                calls.append(target)
                result = pages.get(target, pinned if target == url else OSError('HTTP 403'))
                if isinstance(result, Exception):
                    raise result
                return result
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'data/supplement-sources/manifest.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([dict(file='petscout-locations.lua',
                url='https://www.curseforge.com/wow/addons/petscout-forever/files/8940612',
                download_url=url, archive_sha256=hashlib.sha256(pinned).hexdigest())]))
            result = update.petscout(Fetcher(), root, outcomes)
        return result, outcomes, calls

    def test_blocked_discovery_still_downloads_pinned_zip_and_reports_fallback(self):
        result, outcomes, calls = self.run_source({})
        self.assertEqual(result['names']['companion'], {5005: 'Pinned Pet'})
        self.assertEqual(outcomes[-1]['freshness'], 'pinned-fallback')
        self.assertEqual(outcomes[0]['source'], 'petscout-discovery')
        self.assertEqual(len(calls), 2)
        self.assertTrue(all('/download/' not in url for url in calls))

    def test_new_release_uses_published_filename_and_cdn(self):
        base = 'https://www.curseforge.com/wow/addons/petscout-forever'
        pages = {base + '/files/all': b'<a href="/wow/addons/petscout-forever/files/9000007">new</a>',
                 base + '/files/9000007': b'<div>File name</div><div>PetScoutForever-v0.2-forever.zip</div>',
                 'https://edge.forgecdn.net/files/9000/007/PetScoutForever-v0.2-forever.zip': archive()}
        result, outcomes, calls = self.run_source(pages)
        self.assertEqual(result['names']['companion'], {5005: 'New Pet'})
        self.assertEqual(outcomes[-1]['freshness'], 'latest-listed')
        self.assertEqual(outcomes[-1]['version'], '9000007')
        self.assertEqual(len(calls), 3)
        pages[next(url for url in pages if url.endswith('.zip'))] = b'<html>Download page</html>'
        result, outcomes, _ = self.run_source(pages)
        self.assertEqual(result['names']['companion'], {5005: 'Pinned Pet'})
        self.assertIn('not a ZIP', outcomes[0]['reason'])
        self.assertEqual(outcomes[-1]['freshness'], 'pinned-fallback')

    def test_known_latest_file_uses_pinned_archive_without_detail_page(self):
        index = 'https://www.curseforge.com/wow/addons/petscout-forever/files/all'
        result, outcomes, calls = self.run_source({index: b'/wow/addons/petscout-forever/files/8940612'})
        self.assertEqual(outcomes[-1]['freshness'], 'latest-listed')
        self.assertEqual(len(calls), 2)

    def test_changed_pinned_archive_and_malformed_sources_are_rejected(self):
        url = 'https://edge.forgecdn.net/files/8940/612/PetScoutForever-v0.1.1-forever.zip'
        result, outcomes, _ = self.run_source({url: archive(name='Changed')})
        self.assertIsNone(result)
        self.assertIn('checksum', outcomes[-1]['reason'])
        for raw in (b'<html>not zip</html>', archive(build='12.0.0.12345'), archive(name='|Hunsafe')):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                update.petscout_archive(raw)

    def test_filename_from_embedded_json_and_lua_escaping(self):
        url = update.petscout_file_url(r'{\"fileName\":\"PetScoutForever-v0.3-forever.zip\"}', 9000008)
        self.assertEqual(url, 'https://edge.forgecdn.net/files/9000/008/PetScoutForever-v0.3-forever.zip')
        self.assertEqual(lua_string('a"b\\c\n7'), '"a\\"b\\\\c\\0107"')
        with self.assertRaises(ValueError):
            update.petscout_file_url('File name ../../unsafe.zip', 9000008)


if __name__ == '__main__':
    unittest.main()

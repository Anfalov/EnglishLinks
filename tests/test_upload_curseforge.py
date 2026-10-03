import importlib.util
import io
import json
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "upload_curseforge", Path(__file__).resolve().parents[1] / "tools/upload_curseforge.py")
upload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload)


class UploadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        pub = self.root / 'publishing/curseforge'
        pub.mkdir(parents=True)
        (pub / 'metadata.json').write_text(json.dumps({
            'project_id': 1721401,
            'game_version_source': {'product': 'wow_classic_beta', 'region': 'eu'}}))
        (pub / 'CHANGELOG.md').write_text('## 1.0.1 — today\n\nNew fix.\n\n## 1.0.0\n\nOld change.\n')
        self.archive = self.root / 'EnglishLinks-1.0.1.zip'
        with ZipFile(self.archive, 'w') as z:
            z.writestr('EnglishLinks/EnglishLinks.toc', '## Version: 1.0.1\n')
            z.writestr('EnglishLinks/EnglishLinks.lua', 'local VERSION = "1.0.1"\n')

    def test_exact_zip_and_metadata_are_sent(self):
        with patch.object(upload, 'current_game_version', return_value='1.60.2') as latest:
            project, metadata = upload.prepare_upload(self.root, self.archive, '1.0.1')
            latest.assert_called_once_with({'product': 'wow_classic_beta', 'region': 'eu'})
        original = self.archive.read_bytes()
        with patch.object(upload.request, 'build_opener') as factory:
            opener = factory.return_value
            opener.open.return_value = io.BytesIO(b'{"id": 12345}')
            self.assertEqual(upload.upload(project, metadata, self.archive, 'fake-token'), 12345)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, 'https://wow.curseforge.com/api/projects/1721401/upload-file')
        self.assertEqual(req.get_header('X-api-token'), 'fake-token')
        message = BytesParser(policy=default).parsebytes(
            ('Content-Type: ' + req.get_header('Content-type') + '\r\n\r\n').encode() + req.data)
        parts = list(message.iter_parts())
        self.assertEqual(json.loads(parts[0].get_payload(decode=True)), metadata)
        self.assertEqual(parts[1].get_filename(), self.archive.name)
        self.assertEqual(parts[1].get_payload(decode=True), original)
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertEqual(metadata['gameVersionNames'], ['1.60.2'])
        self.assertEqual(metadata['releaseType'], 'release')
        self.assertEqual(metadata['changelog'], 'New fix.')

    def test_mismatched_version_is_rejected_before_upload(self):
        with ZipFile(self.archive, 'w') as z:
            z.writestr('EnglishLinks/EnglishLinks.toc', '## Version: 1.0.0\n')
            z.writestr('EnglishLinks/EnglishLinks.lua', 'local VERSION = "1.0.0"\n')
        with self.assertRaisesRegex(ValueError, 'runtime version'):
            upload.prepare_upload(self.root, self.archive, '1.0.1')

    def test_http_failure_is_not_retried_or_echoed(self):
        with patch.object(upload.request, 'build_opener') as factory:
            opener = factory.return_value
            opener.open.side_effect = HTTPError('url', 503, 'sensitive response', {}, None)
            with self.assertRaisesRegex(RuntimeError, 'HTTP 503') as caught:
                upload.upload(1721401, {}, self.archive, 'fake-token')
            opener.open.assert_called_once()
            self.assertNotIn('sensitive', str(caught.exception))
            self.assertNotIn('fake-token', str(caught.exception))

    def test_timeout_is_not_retried(self):
        with patch.object(upload.request, 'build_opener') as factory:
            opener = factory.return_value
            opener.open.side_effect = TimeoutError()
            with self.assertRaisesRegex(RuntimeError, 'check CurseForge Files'):
                upload.upload(1721401, {}, self.archive, 'fake-token')
            opener.open.assert_called_once()

    def test_redirect_does_not_forward_token(self):
        self.assertIsNone(upload.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid'))

    def test_missing_version_notes_do_not_include_old_changes(self):
        self.assertEqual(upload.release_notes('## 1.0.0\nOld change.', '1.0.1'),
                         'English Links 1.0.1: maintenance and name database updates.')


class BlizzardVersionTests(unittest.TestCase):
    TABLE = ('Region!STRING:0|BuildConfig!HEX:16|BuildId!DEC:4|VersionsName!String:0\n'
             '## seqn = 4056976\n'
             'us|abc|70300|1.60.2.70300\n'
             'eu|def|70205|1.60.1.70205\n')

    def test_selects_eu_even_if_us_is_newer(self):
        self.assertEqual(upload.parse_blizzard_version(self.TABLE, 'eu'),
                         ('1.60.1', '1.60.1.70205'))

    def test_columns_are_found_by_name(self):
        table = 'BuildId!DEC:4|VersionsName!String:0|Region!STRING:0\r\n70205|1.60.1.70205|eu\r\n'
        self.assertEqual(upload.parse_blizzard_version(table, 'eu')[0], '1.60.1')

    def test_bad_or_ambiguous_response_is_rejected(self):
        for text in ['', '<html>Unavailable</html>', self.TABLE.replace('eu|', 'tw|'),
                     self.TABLE + 'eu|def|70205|1.60.1.70205\n',
                     self.TABLE.replace('1.60.1.70205', '1.60.1.99999'),
                     self.TABLE.replace('1.60.1.70205', '1.60.1'),
                     self.TABLE + 'broken|row\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                upload.parse_blizzard_version(text, 'eu')

    def test_fetch_has_no_curseforge_token_and_uses_configured_product(self):
        with patch.object(upload.request, 'urlopen', return_value=io.BytesIO(self.TABLE.encode())) as get:
            self.assertEqual(upload.current_game_version({'product': 'wow_future', 'region': 'eu'}), '1.60.1')
            req = get.call_args.args[0]
            self.assertEqual(req.full_url, 'https://us.version.battle.net/v2/products/wow_future/versions')
            self.assertFalse(req.has_header('X-api-token'))

    def test_network_failure_stops_instead_of_using_a_stale_version(self):
        with patch.object(upload.request, 'urlopen', side_effect=TimeoutError()):
            with self.assertRaisesRegex(RuntimeError, 'upload stopped'):
                upload.current_game_version({'product': 'wow_classic_beta', 'region': 'eu'})

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/publish_update.sh'
sys.path.insert(0, str(SCRIPT.parent))
from resolve_update_source import resolve


class PublishUpdate(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.remote = self.root / 'remote.git'
        self.repo = self.root / 'work'
        self.git(self.root, 'init', '--bare', str(self.remote))
        self.git(self.root, 'clone', str(self.remote), str(self.repo))
        self.git(self.repo, 'config', 'user.name', 'Test')
        self.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.git(self.repo, 'checkout', '-b', 'main')
        (self.repo / 'EnglishLinks').mkdir()
        (self.repo / 'EnglishLinks/NameData.lua').write_text('baseline')
        (self.repo / 'data').mkdir()
        (self.repo / 'data/source-registry.json').write_text('{}')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-m', 'Initial')
        self.initial = self.git(self.repo, 'rev-parse', 'HEAD')
        self.git(self.repo, 'branch', 'develop')
        self.git(self.repo, 'push', 'origin', 'main', 'develop')
        (self.repo / 'EnglishLinks/NameData.lua').write_text('updated')
        (self.repo / 'data/auto-updates/test').mkdir(parents=True)
        (self.repo / 'data/auto-updates/test/report.json').write_text('{}')

    def git(self, cwd, *args):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def publish(self):
        self.output = self.root / 'outputs'
        env = dict(os.environ, GITHUB_OUTPUT=str(self.output), GITHUB_RUN_ID='123')
        return subprocess.run(['bash', str(SCRIPT)], cwd=self.repo, env=env, capture_output=True, text=True)

    def test_pushes_service_main_and_idle_develop(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        for branch in ('main', 'develop', 'autoupdate'):
            self.assertEqual(self.git(self.remote, 'rev-parse', branch), head)
        self.assertIn('sha=' + head, self.output.read_text())

    def advance(self, branch):
        other = self.root / 'other'
        self.git(self.root, 'clone', '-b', branch, str(self.remote), str(other))
        self.git(other, 'config', 'user.name', 'Test')
        self.git(other, 'config', 'user.email', 'test@example.invalid')
        (other / 'user-work.txt').write_text('User work')
        self.git(other, 'add', '.')
        self.git(other, 'commit', '-m', 'Concurrent work')
        self.git(other, 'push', 'origin', branch)
        return self.git(other, 'rev-parse', 'HEAD')

    def test_concurrent_main_is_never_overwritten_or_released(self):
        user_head = self.advance('main')
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), user_head)
        self.assertFalse(self.output.exists())

    def test_independent_develop_work_is_preserved(self):
        user_head = self.advance('develop')
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'develop'), user_head)
        self.assertNotEqual(self.git(self.remote, 'rev-parse', 'main'), user_head)

    def test_initial_source_and_no_change_result(self):
        expected = dict(source_sha=self.initial, prepared=False, changed=False)
        self.assertEqual(resolve(self.repo, self.initial, '123'), expected)
        self.assertEqual(resolve(self.repo, '', '123'), expected)

    def test_stale_release_source_is_rejected(self):
        latest = self.advance('main')
        self.git(self.repo, 'fetch', 'origin', 'main')
        with self.assertRaisesRegex(ValueError, 'main advanced'):
            resolve(self.repo, self.initial, '123')
        self.assertEqual(resolve(self.repo, '', '123')['source_sha'], latest)

    def test_retry_reuses_published_update_even_after_main_advances(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.git(self.repo, 'rev-parse', 'HEAD')
        self.advance('main')
        self.git(self.repo, 'fetch', 'origin', 'main')
        self.assertEqual(resolve(self.repo, self.initial, '123'),
                         dict(source_sha=updated, prepared=True, changed=True))
        self.assertEqual(resolve(self.repo, '', '123')['source_sha'], updated)
        # Similar run IDs must not match the retry marker.
        with self.assertRaisesRegex(ValueError, 'main advanced'):
            resolve(self.repo, self.initial, '12')
        with self.assertRaisesRegex(ValueError, 'requested source'):
            resolve(self.repo, updated, '123')

    def tag_release(self, source):
        self.git(self.repo, 'reset', '--hard', source)
        self.git(self.repo, 'commit', '--allow-empty', '-m', 'Release 1.0.1',
                 '-m', 'Release-Run-ID: 123')
        self.git(self.repo, 'tag', 'v1.0.1')

    def test_retry_reuses_tag_when_names_did_not_change(self):
        self.tag_release(self.initial)
        self.advance('main')
        self.git(self.repo, 'fetch', 'origin', 'main')
        self.assertEqual(resolve(self.repo, self.initial, '123'),
                         dict(source_sha=self.initial, prepared=True, changed=False))

    def test_retry_reuses_tag_after_name_update(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.git(self.repo, 'rev-parse', 'HEAD')
        self.tag_release(updated)
        self.assertEqual(resolve(self.repo, self.initial, '123'),
                         dict(source_sha=updated, prepared=True, changed=True))

    def test_source_must_be_full_sha(self):
        with self.assertRaisesRegex(ValueError, 'full commit SHA'):
            resolve(self.repo, 'main', '123')


if __name__ == '__main__':
    unittest.main()

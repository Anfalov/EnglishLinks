import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "prepare_release", Path(__file__).resolve().parents[1] / "tools/prepare_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {
            ".github/release-version.json": json.dumps({"base_version": "0.6.1", "run_number_offset": 0}),
            "EnglishLinks/EnglishLinks.toc": "## Version: 0.6.1\nEnglishLinks.lua\n",
            "EnglishLinks/EnglishLinks.lua": 'local VERSION = "0.6.1"\n',
            "README.md": "# EnglishLinks 0.6.1\nHistory: added rand in 0.6.1.\n",
            "NOTICE": "EnglishLinks 0.6.1\nSource added in 0.6.1.\n",
            "EnglishLinks/NOTICE": "EnglishLinks 0.6.1\nSource added in 0.6.1.\n",
            "EnglishLinks/README-en.md": "# EnglishLinks 0.6.1\nInstall.\n",
            "EnglishLinks/README-ru.md": "# EnglishLinks 0.6.1\nУстановка.\n",
            "publishing/curseforge/metadata.json": json.dumps({"version": "0.6.1", "game_versions": ["1.60.1"]}),
            "publishing/curseforge/UPLOAD.md": "Upload EnglishLinks-0.6.1.zip for game 1.60.1.\n",
            "CHANGELOG.md": "## 0.6.1\nHistorical changes.\n",
        }
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git("init", "-q")
        self.git("config", "user.name", "Release test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "Source")
        self.source = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return release.git(self.root, *args)

    def test_monotonic_versions_and_retry(self):
        config = {"base_version": "0.6.1", "run_number_offset": 0}
        self.assertEqual(release.version_for_run(config, 1), "0.6.2")
        self.assertEqual(release.version_for_run(config, 2), "0.6.3")
        self.assertEqual(release.version_for_run(config, 1), "0.6.2")
        self.assertEqual(release.version_for_run(
            {"base_version": "0.7.0", "run_number_offset": 20}, 21), "0.7.1")
        with self.assertRaises(ValueError):
            release.version_for_run(config, 0)

    def test_stamp_updates_runtime_and_metadata_but_preserves_history(self):
        version, tag = release.prepare(self.root, 1, "123", self.source)
        self.assertEqual((version, tag), ("0.6.2", "v0.6.2"))
        self.assertIn('VERSION = "0.6.2"', (self.root / "EnglishLinks/EnglishLinks.lua").read_text())
        self.assertIn("Version: 0.6.2", (self.root / "EnglishLinks/EnglishLinks.toc").read_text())
        metadata = json.loads((self.root / "publishing/curseforge/metadata.json").read_text())
        self.assertEqual(metadata["version"], "0.6.2")
        self.assertEqual(metadata["upload_file"], "EnglishLinks-0.6.2.zip")
        self.assertEqual(metadata["game_versions"], ["1.60.1"])
        self.assertEqual((self.root / "README.md").read_text(),
                         "# EnglishLinks 0.6.2\nHistory: added rand in 0.6.1.\n")
        self.assertIn("## 0.6.1", (self.root / "CHANGELOG.md").read_text())

    def test_retry_uses_existing_tag_and_does_not_change_main(self):
        branch = self.git("branch", "--show-current")
        self.git("checkout", "--detach", self.source)
        release.prepare(self.root, 1, "123", self.source)
        self.git("add", "-u")
        self.git("commit", "-qm", "Release 0.6.2\n\nRelease-Run-ID: 123")
        self.git("tag", "v0.6.2")
        tagged = self.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", self.source)
        self.assertEqual(release.prepare(self.root, 1, "123", self.source), ("0.6.2", "v0.6.2"))
        self.assertEqual(self.git("rev-parse", "HEAD"), tagged)
        self.assertEqual(self.git("rev-parse", branch), self.source)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_collision_is_not_overwritten(self):
        self.git("commit", "--allow-empty", "-qm", "Another release")
        self.git("tag", "v0.6.2")
        tagged = self.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", self.source)
        with self.assertRaisesRegex(ValueError, "another release"):
            release.prepare(self.root, 1, "123", self.source)
        self.assertEqual(self.git("rev-parse", "v0.6.2"), tagged)

    def test_dirty_tree_is_rejected(self):
        (self.root / "README.md").write_text("Uncommitted change\n")
        with self.assertRaisesRegex(ValueError, "clean working tree"):
            release.prepare(self.root, 1, "123", self.source)


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from lupa.lua51 import LuaRuntime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_quests as b


class Quests(unittest.TestCase):
    def fixture(self, root):
        sources = {
            'questiedb/foreverQuestDB.lua': '[1] = {"Inherited",{}},\n[99] = {"Outside Forever",{}},',
            'questiedb/foreverBaseQuest.lua': '[2] = {\n [questKeys.name] = "New Quest",\n},',
            'EverythingQuests/QuestAvailable_Forever.lua': 'names = {\n[2]="Alternative",\n[3]="Third",\n}',
            'Completao/ForeverNew.lua': '{ id = 4, name = "Chain (1/2)", level = 1 },',
        }
        manifest = []
        for file, text in sources.items():
            path = root / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            manifest.append(dict(file=file, sha256=hashlib.sha256(text.encode()).hexdigest()))
        (root / 'manifest.json').write_text(json.dumps(manifest))
    def test_priority_annotations_and_lua(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            names, provenance, report = b.compile_quests(root)
            self.assertEqual(names, {1:'Inherited', 2:'New Quest', 3:'Third', 4:'Chain', 99:'Outside Forever'})
            self.assertEqual(report['conflicts'][0]['alternative'], 'Alternative')
            runtime = LuaRuntime()
            ns = runtime.table()
            runtime.execute(b.render(names, '1.60.1.70124', report), 'EnglishLinks', ns)
            self.assertEqual(dict(ns.Names.quest.items()), names)

    def test_source_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / 'Completao/ForeverNew.lua').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                b.compile_quests(root)

    def test_escaped_title_and_markup_rejection(self):
        title = 'Quest "quoted" \\ é'
        self.assertEqual(b.decode_string(json.dumps(title)), title)
        with self.assertRaisesRegex(ValueError, 'Invalid quest title'):
            b.decode_string('"|Hquest:1|hBad|h"')


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class QuestieLinks(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        for name in ('NameData', 'LinkText', 'Resolver'):
            self.lua.execute((ROOT / 'EnglishLinks' / (name + '.lua')).read_text(), 'EnglishLinks', self.ns)
        self.ns.InitDB(self.lua.table())

    def test_tracker_and_journey_text_formats_translate_before_sending(self):
        # Formats emitted by Questie's TrackerData.GetQuestLink and
        # QuestieLink.GetQuestLinkStringById (Questie commit 7df91a1).
        for original in ['[Уборка в лагере кобольдов (7)]',
                         '[[2] Уборка в лагере кобольдов (7)]',
                         '[[-1] Уборка в лагере кобольдов (0007)]']:
            expected = original.replace('Уборка в лагере кобольдов', 'Kobold Camp Cleanup')
            translated, cursor, count = self.ns.TranslateQuestie(original, self.ns.Resolve, len(original.encode()))
            self.assertEqual((translated, cursor, count), (expected, len(expected.encode()), 1))
            self.assertEqual(self.ns.TranslateQuestie(translated, self.ns.Resolve, cursor), (expected, cursor, 0))

    def test_cursor_inside_title_and_mixed_message(self):
        original = 'До [заметка] [[2] Уборка (7)] и [Уборка (7)] после'
        expected = original.replace('Уборка', 'Kobold Camp Cleanup')
        start = len(original[:original.index('Уборка')].encode())
        result, cursor, count = self.ns.TranslateQuestie(original, self.ns.Resolve, start + 2)
        self.assertEqual(result, expected)
        self.assertEqual(cursor, start + len('Kobold Camp Cleanup'))
        self.assertEqual(count, 2)
        self.assertEqual(self.ns.TranslateQuestie(original, self.ns.Resolve, 1)[1], 1)

    def test_payloads_labels_and_escaped_markup_are_not_plain_questie_text(self):
        protected = [
            '|Hplayer:Person|h[Уборка (7)]|h',
            '|Hquest:7:2|h[Уборка (7)]|h',
            '||Hquest:7:2|h[Уборка (7)]|h',
            '|Hquest:7:2|h[Уборка (7)]',
            '|T[Уборка (7)]:16|t', '|A:[Уборка (7)]:16:16|a',
        ]
        for prefix in protected:
            self.assertEqual(self.ns.TranslateQuestie(prefix, self.ns.Resolve)[0], prefix)
        message = protected[0] + ' [Уборка (7)]'
        self.assertEqual(self.ns.TranslateQuestie(message, self.ns.Resolve)[0],
                         protected[0] + ' [Kobold Camp Cleanup (7)]')

    def test_unknown_id_type_switch_and_manual_override(self):
        missing = []
        message = '[Нет в базе (2147483647)]'
        self.assertEqual(self.ns.TranslateQuestie(message, self.ns.Resolve, None,
                         lambda kind, identifier: missing.append((kind, identifier)))[0], message)
        self.assertEqual(missing, [('quest', 2147483647)])
        self.ns.DB.types.quest = False
        self.assertEqual(self.ns.TranslateQuestie('[Уборка (7)]', self.ns.Resolve)[0], '[Уборка (7)]')
        self.ns.DB.types.quest = True
        self.ns.DB.typedOverrides.quest[7] = 'Custom Quest'
        self.assertEqual(self.ns.TranslateQuestie('[Уборка (7)]', self.ns.Resolve)[0], '[Custom Quest (7)]')


if __name__ == '__main__':
    unittest.main()

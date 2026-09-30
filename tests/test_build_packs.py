import csv
from pathlib import Path
import sys
import tempfile
import unittest
from lupa.lua51 import LuaRuntime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_packs as b

BUILD='1.60.1.70009'
class Packs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def write(self,table,header,rows,build=BUILD):
        p=self.root/(table+'.'+build+'.csv')
        with p.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(header);w.writerows(rows)
        return p
    def core(self):
        self.write('SpellName',['ID','Name_lang'],[(10,'Fire "ball"'),(11,'Rank 2')])
        self.write('SkillLine',['ID','DisplayName_lang'],[(10,'Alchemy')])
        self.write('Achievement',['ID','Title_lang'],[(10,'Achievement')])
    def compile(self,**kw): return b.compile_directory(self.root,BUILD,**kw)
    def test_all_schemas_and_roundtrip(self):
        for table,(_,field) in b.DIRECT.items(): self.write(table,['ID',field],[(10,'Name "quoted" \\ UTF8 é')])
        self.write('Mount',['ID','Name_lang','SourceSpellID'],[(10,'Brown Horse',458)])
        self.write('Creature',['ID','Name_lang'],[(100,'Species')])
        self.write('BattlePetSpecies',['ID','CreatureID'],[(10,100),(11,999)])
        self.write('Talent',['ID','SpellRank_0','SpellRank_1'],[(20,10,11)])
        self.write('SkillLineAbility',['ID','Spell','SkillLine'],[(1,10,10),(2,11,10),(3,11,20)])
        self.write('QuestV2',['ID','UniqueBitFlag'],[(30,1),(20,2)])
        out=self.compile(); names,rel,quests,sources,_=out
        self.assertEqual(names['companion'],{10:'Species'})
        self.assertEqual(names['mount'],{458:'Brown Horse'})
        self.assertEqual(rel['talent'][20],[10,11]);self.assertEqual(rel['recipe'],{10:10})
        self.assertEqual(quests,[20,30]);self.assertEqual(len(sources),len(b.DIRECT)+5)
        runtime=LuaRuntime();ns=runtime.table();runtime.execute(b.render(out,BUILD),'EnglishLinks',ns)
        self.assertEqual(ns.Names.spell[10],'Name "quoted" \\ UTF8 é')
        self.assertEqual(ns.Relations.talent[20][2],11)
        self.assertEqual(ns.PackMeta.spell.build,BUILD)
    def test_required(self):
        self.write('SpellName',['ID','Name_lang'],[(1,'Test')])
        with self.assertRaisesRegex(ValueError,'Missing required'): self.compile()
        self.assertEqual(self.compile(allow_partial=True)[0]['spell'],{1:'Test'})
    def test_wrong_build(self):
        self.core();self.write('UiMap',['ID','Name_lang'],[(1,'Map')],build='1.15.0.1')
        with self.assertRaisesRegex(ValueError,'Wrong build'): self.compile()
        with self.assertRaisesRegex(ValueError,'Forever build'): b.compile_directory(self.root,'1.15.0.1')
    def test_duplicate_and_missing_columns(self):
        self.core();self.write('SpellName',['ID','Wrong'],[(1,'A')])
        with self.assertRaisesRegex(ValueError,'requires columns'): self.compile()
        self.write('SpellName',['ID','Name_lang'],[(1,'A'),(1,'B')])
        with self.assertRaisesRegex(ValueError,'Duplicate IDs'): self.compile()
    def test_reject_markup(self):
        self.core();self.write('SpellName',['ID','Name_lang'],[(1,'|Hspell:1|hBad|h')])
        with self.assertRaisesRegex(ValueError,'Invalid name'): self.compile()
    def test_pet_join_required(self):
        self.core();self.write('BattlePetSpecies',['ID','CreatureID'],[(1,100)])
        with self.assertRaisesRegex(ValueError,'needs Creature'): self.compile()
    def test_modern_talent_and_no_input(self):
        with self.assertRaisesRegex(ValueError,'No supported'): self.compile(allow_partial=True)
        self.core();self.write('Talent',['ID','SpellID'],[(20,10)])
        self.assertEqual(self.compile()[1]['talent'],{20:10})

if __name__=='__main__': unittest.main()

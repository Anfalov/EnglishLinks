import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import catalog_sources as catalogs
import update_names as u


class CatalogUpdate(unittest.TestCase):
    def test_broken_gear_does_not_drop_other_tables_or_skills(self):
        class Fake:
            def get(self, url, source):
                if url.endswith('global'):
                    return (b'WH.setPageData("url.dataPageVersions",{"gear-planner":74,"achievements":12});'
                            b'WH.setPageData("wow.currency.namesAndIcons",{"9":{"id":9,"name":"Coin"}});'
                            b'WH.setPageData("wow.skill.names",{"171":"Alchemy"});')
                if 'gear-planner' in url:
                    raise OSError('unavailable')
                if url.endswith('achievements?dv=12'):
                    return b'var _ = g_achievements;\n_[9]={"id":9,"name":"Victory"};'
                raise AssertionError(url)
        rows = []
        primary, conflicts = u.combine_primary(catalogs.bulk(Fake(), rows))
        self.assertEqual(conflicts, [])
        self.assertEqual(primary['names'], {'achievement': {9:'Victory'}, 'currency': {9:'Coin'},
                                            'profession': {171:'Alchemy'}})
        self.assertTrue(any('gear-planner' in r['source'] and r['status']=='skipped' for r in rows))

    def test_shared_cutoff_and_restart_with_overlapping_ids(self):
        class Fake:
            def get(self, url, source):
                kind = url.split('/')[-2]
                key = int(url.split('/')[-1].split('?')[0])
                calls.append((kind,key))
                return json.dumps({'name':kind.title() + str(key)}).encode()
        current = u.named('quest', {8:'Prior quest'})
        primary = u.named('item', {10:'Bulk name'})
        maps = {'item':{7,10}, 'spell':{7}, 'achievement':{7}, 'currency':{7}, 'profession':{11}}
        extra = [('other',u.named('spell',{7:'Fallback'}))]
        rows, calls = [], []
        with patch.object(u, 'TOOLTIP_WORKERS', 1), patch.object(u.time, 'monotonic', lambda: len(calls)):
            updated, pending = u.tooltip_scan(Fake(),current,primary,extra,rows,maps,[('quest',8)],2,0)
            self.assertEqual(calls,[('achievement',7),('currency',7)])
            self.assertEqual(pending,[('item',7),('spell',7),('quest',8)])
            merged, _ = u.name_data.merge(current, updated, extra)
            self.assertEqual(merged['names']['spell'][7], 'Fallback')
            self.assertTrue(any(r.get('missing_ids') == [11] for r in rows))
            with tempfile.TemporaryDirectory() as td:
                path = Path(td)/'pending.json'
                path.write_text(json.dumps(pending))
                queue = u.read_progress(path)
                path.write_text('[1,2]')
                self.assertEqual(u.read_progress(path),[('quest',1),('quest',2)])
            calls.clear()
            refreshed, remaining = u.tooltip_scan(Fake(),merged,primary,extra,[],maps,queue,interval=0)
            self.assertEqual(calls[:3],[('item',7),('spell',7),('quest',8)])
            self.assertEqual(remaining,[])
            self.assertEqual(refreshed['names']['spell'][7],'Spell7')
            self.assertNotIn(('item',10),calls)

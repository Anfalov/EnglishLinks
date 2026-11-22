import json
import sys
from unittest.mock import patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import quest_sitemap as sitemap
import source_health
import update_names as update


class Discovery(unittest.TestCase):
    def test_extra_page_and_partial_index(self):
        def xml(root, tag, urls):
            return (f'<{root} xmlns="{sitemap.NS[1:-1]}">' +
                    ''.join(f'<{tag}><loc>{url}</loc></{tag}>' for url in urls) +
                    f'</{root}>').encode()
        class Fake:
            def get(self, url, source):
                if url == sitemap.PAGE + '2' and self.partial:
                    raise OSError('Unavailable')
                if url.endswith('/sitemap'):
                    return xml('sitemapindex', 'sitemap', [sitemap.PAGE + str(i) for i in (1, 2)])
                return xml('urlset', 'url', ['https://www.wowhead.com/forever/quest=' + url[-1] + '/slug'])
        for partial in (False, True):
            outcomes = []
            fake = Fake()
            fake.partial = partial
            ids = sitemap.discover(fake, outcomes)
            self.assertEqual(ids, {1} if partial else {1, 2})
            self.assertEqual(bool(source_health.problems(outcomes)), partial)

    def test_sitemap_only_id_and_community_fallback(self):
        class Fake:
            def get(self, url, source):
                return b'{"name":"Actual English title"}' if '/7?' in url else b'{"error":"missing"}'
        other = [('community', update.named('quest', {8: 'Other title', 9: 'Wrong'}))]
        current = update.named('quest', {9: 'Retained'})
        primary = update.quest_tooltips(Fake(), current, update.empty(), other, [], interval=0, sitemap_ids={7})
        merged, _ = update.name_data.merge(current, primary, other)
        self.assertEqual(merged['names']['quest'], {7: 'Actual English title', 8: 'Other title', 9: 'Retained'})

    def test_partial_sources_are_not_hidden_by_success(self):
        health = source_health.problems([
            dict(source='questie', status='parsed'),
            dict(source='petscout', status='parsed', freshness='pinned-fallback'),
            dict(source='wowhead', status='skipped', reason='HTTP Error 403: Forbidden'),
            dict(source='wowhead', status='partial', reason='Incomplete'),
        ])
        self.assertEqual(sum(health.values()), 3)
        self.assertTrue(any(reason == 'HTTP 403' for _, _, _, reason in health))

    def test_deadline_with_healthy_server_reports_and_resumes_unvisited_ids_first(self):
        calls = []
        clock = [0.]
        class Fake:
            def get(self, url, source):
                key = int(url.split('/')[-1].split('?')[0])
                calls.append(key)
                clock[0] += 1
                return json.dumps({'name': f'Title {key}'}).encode()
        with patch.object(update, 'TOOLTIP_WORKERS', 1), patch.object(update.time, 'monotonic', lambda: clock[0]):
            rows = []
            base = update.named('quest', {i: f'Title {i}' for i in range(1, 6)})
            first = update.quest_tooltips(Fake(), base, update.empty(), [], rows, interval=0, deadline=2.)
            self.assertFalse(update.name_data.merge(base, first, [])[1])  # no name changes
            self.assertTrue(source_health.problems(rows))
            self.assertEqual((rows[-1]['reason'], rows[-1]['parsed'], rows[-1]['not_requested']),
                             ('time budget reached', 2, 3))
            pending = rows[-1]['pending_ids']
            self.assertEqual(pending, [3, 4, 5])
            calls.clear()
            update.quest_tooltips(Fake(), base, update.empty(), [], rows, interval=0, pending=pending)
            self.assertEqual(calls, [3, 4, 5, 1, 2])
            self.assertEqual(rows[-1]['pending_ids'], [])

    def test_missing_names_precede_even_pending_known_ids(self):
        calls = []
        class Fake:
            def get(self, url, source):
                calls.append(int(url.split('/')[-1].split('?')[0]))
                return b'{"name":"Fresh name"}'
        current = update.named('quest', {1: 'Known', 2: 'Known'})
        primary = update.named('quest', {30: 'Already fetched'})
        extra = [('community', update.named('quest', {25: 'Community name'}))]
        with patch.object(update, 'TOOLTIP_WORKERS', 1):
            update.quest_tooltips(Fake(), current, primary, extra, [], interval=0,
                                  sitemap_ids={20, 30}, pending=[2, 29, 30, 28])
        self.assertEqual(calls, [29, 28, 20, 25, 2, 1])

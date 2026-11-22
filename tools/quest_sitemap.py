"""Read quest IDs (never derive display names from URL slugs)."""
import re
from xml.etree import ElementTree as ET

PAGE = 'https://www.wowhead.com/forever/sitemap/quest?page='
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def locations(raw, root_name, entry):
    root = ET.fromstring(raw)
    if root.tag != NS + root_name:
        raise ValueError('Unexpected sitemap root: ' + root.tag)
    return [node.text or '' for node in root.findall(NS + entry + '/' + NS + 'loc')]


def quest_ids(raw):
    ids = set()
    for url in locations(raw, 'urlset', 'url'):
        m = re.fullmatch(r'https://www\.wowhead\.com/forever/quest=([1-9][0-9]*)(?:/[^?#]*)?', url)
        if not m or int(m[1]) > 2147483647:
            raise ValueError('Invalid Forever quest URL')
        ids.add(int(m[1]))
    if not ids:
        raise ValueError('Empty quest sitemap')
    return ids

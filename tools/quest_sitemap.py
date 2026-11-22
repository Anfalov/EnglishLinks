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


def discover(fetcher, outcomes):
    """Always check page 1; the global index advertises any additional pages."""
    ids = set()
    source = 'wowhead-quest-sitemap'

    def page(n):
        url = PAGE + str(n)
        try:
            found = quest_ids(fetcher.get(url, source))
            ids.update(found)
            outcomes.append(dict(source=source, url=url, status='parsed', count=len(found)))
        except Exception as error:
            outcomes.append(dict(source=source, url=url, status='skipped', reason=str(error)))

    page(1)
    url = 'https://www.wowhead.com/sitemap'
    try:
        pages = {int(m[1]) for loc in locations(fetcher.get(url, source), 'sitemapindex', 'sitemap')
                 if (m := re.fullmatch(re.escape(PAGE) + r'([1-9][0-9]*)', loc))}
        if 1 not in pages:
            raise ValueError('Index has no Forever quest sitemap')
        outcomes.append(dict(source=source, url=url, status='parsed', pages=len(pages)))
        for n in sorted(pages - {1}):
            page(n)
    except Exception as error:
        outcomes.append(dict(source=source, url=url, status='skipped', reason=str(error)))
    return ids

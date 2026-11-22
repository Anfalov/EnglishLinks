"""Public Forever sitemaps and bulk name tables. Downloaded JS is parsed as data."""
import json
import re
from xml.etree import ElementTree as ET

from build_random_affixes import parse as affixes
from build_supplements import gear_items
from name_data import validate

WWW = 'https://www.wowhead.com'
DATA = 'https://nether.wowhead.com/forever/data/'
KINDS = ('quest', 'achievement', 'currency', 'item', 'spell', 'profession')
TYPES = {k: ('skill' if k == 'profession' else k) for k in KINDS}
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def locations(raw, root_name, entry):
    root = ET.fromstring(raw)
    if root.tag != NS + root_name:
        raise ValueError('Unexpected sitemap root: ' + root.tag)
    return [node.text or '' for node in root.findall(NS + entry + '/' + NS + 'loc')]


def discover(fetcher, outcomes, kinds=KINDS):
    index = WWW + '/sitemap'
    try:
        urls = locations(fetcher.get(index, 'wowhead-index-sitemap'), 'sitemapindex', 'sitemap')
        outcomes.append(dict(source='wowhead-index-sitemap', url=index, status='parsed'))
    except Exception as error:
        urls = []
        outcomes.append(dict(source='wowhead-index-sitemap', url=index, status='skipped', reason=str(error)))
    ids = {}
    for kind in kinds:
        typ = TYPES[kind]
        source = f'wowhead-{kind}-sitemap'
        prefix = f'{WWW}/forever/sitemap/{typ}?page='
        pages = {int(m[1]) for url in urls if (m := re.fullmatch(re.escape(prefix) + r'([1-9]\d*)', url))}
        if urls and 1 not in pages:
            outcomes.append(dict(source=source, url=index, status='partial', reason='Missing first page in index'))
        ids[kind] = set()
        for n in sorted(pages | {1}):
            url = prefix + str(n)
            try:
                found = set()
                for loc in locations(fetcher.get(url, source), 'urlset', 'url'):
                    m = re.fullmatch(re.escape(f'{WWW}/forever/{typ}=') + r'([1-9]\d*)(?:/[^?#]*)?', loc)
                    if not m or int(m[1]) > 2147483647:
                        raise ValueError('Invalid Forever permalink')
                    found.add(int(m[1]))
                if not found:
                    raise ValueError('Empty sitemap')
                ids[kind].update(found)
                outcomes.append(dict(source=source, url=url, status='parsed', count=len(found)))
            except Exception as error:
                outcomes.append(dict(source=source, url=url, status='skipped', reason=str(error)))
    return ids


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate key in Wowhead data')
        out[key] = value
    return out


def table(text, key):
    marker = f'WH.setPageData("{key}",'
    if text.count(marker) != 1:
        raise ValueError(f'Missing or ambiguous: {key}')
    return json.JSONDecoder(object_pairs_hook=unique).raw_decode(text.split(marker)[1].lstrip())[0]


def indexed(rows, field=None):
    result = {}
    for key, row in rows.items():
        if not re.fullmatch(r'[1-9]\d*', key) or (field and row['id'] != int(key)):
            raise ValueError(f'Invalid or mismatched ID: {key}')
        result[int(key)] = row[field] if field else row
    return result


def achievements(text):
    if not text.startswith('var _ = g_achievements;'):
        raise ValueError('Not a Forever achievement table')
    decoder = json.JSONDecoder(object_pairs_hook=unique)
    return indexed(unique((m[1], decoder.raw_decode(text, m.end())[0])
                          for m in re.finditer(r'_\[(\d+)\]=(?=\{)', text)), 'name')


def bulk(fetcher, outcomes):
    """Keep each validated table even if another download/table fails."""
    parts = []
    def download(key, url):
        try:
            return fetcher.get(url, 'wowhead-bulk-' + key).decode()
        except Exception as error:
            outcomes.append(dict(source='wowhead-bulk-'+key, url=url, status='skipped', reason=str(error)))
    def parse(kind, text, url, reader):
        try:
            rows = reader(text)
            if not rows:
                raise ValueError('Empty name table')
            part = dict(names={}, bonuses={}, random_affixes={})
            if kind == 'random_affixes':
                part[kind] = rows
            else:
                part['names'][kind] = rows
            validate(part)
            parts.append(part)
            outcomes.append(dict(source='wowhead-bulk-'+kind, url=url, status='parsed', count=len(rows)))
        except Exception as error:
            outcomes.append(dict(source='wowhead-bulk-'+kind, url=url, status='skipped', reason=str(error)))
    url = DATA + 'global'
    global_data = download('global', url)
    versions = {}
    if global_data is not None:
        parse('profession', global_data, url, lambda s: indexed(table(s, 'wow.skill.names')))
        parse('currency', global_data, url, lambda s: indexed(table(s, 'wow.currency.namesAndIcons'), 'name'))
        try:
            versions = table(global_data, 'url.dataPageVersions')
            if not isinstance(versions, dict):
                raise ValueError('Invalid versions table')
        except ValueError as error:
            versions = {}
            outcomes.append(dict(source='wowhead-bulk-versions', url=url, status='partial', reason=str(error)))
    for key, readers in [('gear-planner', [('item', gear_items), ('random_affixes', affixes)]),
                         ('achievements', [('achievement', achievements)])]:
        dv = versions.get(key)
        url = DATA + key + (f'?dv={dv}' if type(dv) is int and dv > 0 else '')
        raw = download(key, url)
        if raw is not None:
            for kind, reader in readers:
                parse(kind, raw, url, reader)
    return parts

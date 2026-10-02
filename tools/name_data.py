"""The installed Lua dictionary is the starting point for incremental updates."""
from copy import deepcopy
from pathlib import Path
from lupa.lua51 import LuaRuntime
from build_packs import lua, name_ok

FIELDS = {'names': 'Names', 'bonuses': 'ItemBonusSuffixes',
          'random_affixes': 'ItemRandomAffixes', 'relations': 'Relations'}
KINDS = {'item', 'spell', 'quest', 'profession', 'achievement', 'currency',
         'companion', 'mount', 'talent'}


def python_table(table):
    return {k: python_table(v) if hasattr(v, 'items') else v for k, v in table.items()}


def from_namespace(ns):
    data = {key: python_table(ns[field]) if ns[field] is not None else {}
            for key, field in FIELDS.items()}
    validate(data)
    return data


def load(path):
    # Only our committed addon file is executed. Downloaded sources are parsed
    # as data by update_names.py, never passed to Lua or JavaScript runtimes.
    runtime = LuaRuntime(unpack_returned_tuples=True)
    ns = runtime.table()
    runtime.execute(Path(path).read_text(), 'EnglishLinks', ns)
    return from_namespace(ns)


def validate(data):
    if set(data) != set(FIELDS) or not set(data['names']) <= KINDS:
        raise ValueError('Unexpected dictionary sections')
    for section in ('names', 'bonuses', 'random_affixes'):
        groups = data[section].values() if section == 'names' else [data[section]]
        for rows in groups:
            for key, value in rows.items():
                if type(key) is not int or not 0 < abs(key) <= 2147483647:
                    raise ValueError('Invalid ID')
                if section != 'random_affixes' and key < 0:
                    raise ValueError('Unexpected negative ID')
                if section == 'bonuses' and value == '':
                    continue
                if not isinstance(value, str) or not name_ok(value):
                    raise ValueError('Unsafe name')


def render(data):
    validate(data)
    lines = ['-- Prepared names. Updated incrementally by tools/update_names.py.',
             'local _, ns = ...']
    # One ID per line keeps Git changes reviewable even though serialization
    # writes the whole file. No timestamps or source-order churn in the addon.
    def rows(values, indent):
        return [indent + '[' + lua(key) + '] = ' + lua(value) + ','
                for key, value in sorted(values.items())]
    lines.append('ns.Names = {')
    for kind, values in sorted(data['names'].items()):
        lines.append('    [' + lua(kind) + '] = {')
        lines += rows(values, '        ')
        lines.append('    },')
    lines.append('}')
    for key in ('bonuses', 'random_affixes'):
        lines.append('ns.' + FIELDS[key] + ' = {')
        lines += rows(data[key], '    ')
        lines.append('}')
    lines.append('ns.Relations = ' + lua(data['relations']))
    lines += ['ns.PackMeta = {}', 'for kind, entries in pairs(ns.Names) do',
              '    local count = 0', '    for _ in pairs(entries) do count = count + 1 end',
              '    ns.PackMeta[kind] = {count=count, locale="enUS", coverage="prepared"}',
              'end', '']
    return '\n'.join(lines)


def merge(current, primary, supplements):
    """Never remove IDs. Only primary names may replace an existing label."""
    result = deepcopy(current)
    changes = []
    for source, incoming, overwrite in [('wowhead', primary, True)] + [
            (source, rows, False) for source, rows in supplements]:
        for section in ('names', 'bonuses', 'random_affixes'):
            groups = incoming.get(section, {})
            groups = groups.items() if section == 'names' else [(section, groups)]
            for kind, rows in groups:
                target = result['names'].setdefault(kind, {}) if section == 'names' else result[section]
                for key, value in sorted(rows.items()):
                    if key not in target or (overwrite and target[key] != value):
                        changes.append(dict(section=section, kind=kind, id=key,
                                            before=target.get(key), after=value, source=source))
                        target[key] = value
    validate(result)
    return result, changes

"""Validation and Lua 5.1 serialization shared by source parsers."""
import re


def lua_string(value):
    # Lua 5.1 has decimal escapes, not JSON's \uXXXX escape notation.
    out = []
    for char in str(value):
        if char in ('"', '\\'):
            out.append('\\' + char)
        elif ord(char) < 32 or ord(char) == 127:
            out.append('\\%03d' % ord(char))
        else:
            out.append(char)
    return '"' + ''.join(out) + '"'

def name_ok(name):
    return (bool(name.strip()) and len(name.encode('utf-8')) <= 255
            and not any(ord(c) < 32 or ord(c) == 127 or c == '|' for c in name))

def number(raw, allow_zero=False):
    if not re.fullmatch(r'\d+', str(raw or '')): raise ValueError('Invalid integer ID: %r' % raw)
    n = int(raw)
    if n < (0 if allow_zero else 1) or n > 2147483647: raise ValueError('Out-of-range ID: %s' % n)
    return n

def lua(value):
    if isinstance(value, str): return lua_string(value)
    if isinstance(value, int): return str(value)
    if isinstance(value, list): return '{' + ','.join(lua(v) for v in value) + '}'
    return '{' + ','.join('['+lua(k)+']='+lua(v) for k,v in sorted(value.items())) + '}'

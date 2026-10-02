#!/usr/bin/env python3
"""Package the prepared addon. Never download or rebuild its dictionaries."""
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, source in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None


def main():
    addon = ROOT / 'EnglishLinks'
    toc = (addon / 'EnglishLinks.toc').read_text()
    version = re.search(r'^## Version: (\S+)$', toc, re.M).group(1)
    assert f'local VERSION = "{version}"' in (addon / 'EnglishLinks.lua').read_text()
    for line in toc.splitlines():
        if line and not line.startswith('#'):
            assert (addon / line).is_file(), f'Missing TOC file: {line}'
    assert (addon / 'Icon.tga').is_file()
    for name in ['LICENSE', 'NOTICE']:
        assert (addon / name).is_file(), name
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    install = output / f'EnglishLinks-{version}.zip'
    # Runtime files plus required licenses/notices. Documentation, screenshots,
    # source snapshots and publishing materials are not installable addon data.
    names = ['EnglishLinks.toc', 'Icon.tga', 'LICENSE', 'NOTICE']
    names += [line for line in toc.splitlines() if line and not line.startswith('#')]
    files = [addon / name for name in names] + sorted((addon / 'licenses').glob('*.txt'))
    assert all(p.resolve().is_relative_to(addon.resolve()) for p in files)
    entries = {p.relative_to(ROOT).as_posix(): p for p in files}
    write_zip(install, entries)

    print(f'{install}: {install.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()

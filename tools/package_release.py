#!/usr/bin/env python3
"""Build an installable addon ZIP and a separate CurseForge author kit."""
from pathlib import Path
import hashlib
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
    for name in ['LICENSE', 'NOTICE', 'README-en.md', 'README-ru.md']:
        assert (addon / name).is_file(), name
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    install = output / f'EnglishLinks-{version}.zip'
    entries = {p.relative_to(ROOT).as_posix(): p for p in addon.rglob('*') if p.is_file()}
    assert all(p.suffix in {'.lua', '.toc', '.md', '.txt', '.tga', ''} for p in entries.values())
    write_zip(install, entries)

    kit = output / f'EnglishLinks-{version}-CurseForge-kit.zip'
    assets = {p.name: p for p in (ROOT / 'publishing/curseforge').iterdir() if p.is_file()}
    assets.update({
        install.name: install,
        'englishlinks-icon.png': ROOT / 'docs/images/englishlinks-icon.png',
        'english-links-in-game.jpg': ROOT / 'docs/images/english-links-in-game.jpg',
    })
    write_zip(kit, assets)
    sums = output / f'EnglishLinks-{version}-SHA256SUMS.txt'
    sums.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in [install, kit]))
    for path in [install, kit, sums]:
        print(f'{path}: {path.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()

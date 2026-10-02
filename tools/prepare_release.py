#!/usr/bin/env python3
"""Stamp a release snapshot; never push or modify the main branch."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def version_for_run(config, run_number):
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", config["base_version"])
    if not match:
        raise ValueError("base_version must be a plain major.minor.patch version")
    offset = config["run_number_offset"]
    if type(offset) is not int or offset < 0 or run_number < 1 or run_number < offset:
        raise ValueError("run_number must be positive and at least the nonnegative offset")
    major, minor, patch = map(int, match.groups())
    return f"{major}.{minor}.{patch + run_number - offset}"


def stamp_version(root, version):
    """Update current-version fields, leaving historical changelogs intact."""
    toc_path = root / "EnglishLinks/EnglishLinks.toc"
    toc = toc_path.read_text()
    old = re.search(r"^## Version: (\d+\.\d+\.\d+)$", toc, re.M).group(1)
    lua_path = root / "EnglishLinks/EnglishLinks.lua"
    lua = lua_path.read_text()
    if f'local VERSION = "{old}"' not in lua:
        raise ValueError("TOC and Lua versions disagree")
    toc_path.write_text(toc.replace(f"## Version: {old}", f"## Version: {version}", 1))
    lua_path.write_text(lua.replace(f'local VERSION = "{old}"', f'local VERSION = "{version}"', 1))
    for relative in ["README.md", "NOTICE", "EnglishLinks/NOTICE",
                     "EnglishLinks/README-en.md", "EnglishLinks/README-ru.md"]:
        path = root / relative
        first, rest = path.read_text().split("\n", 1)
        path.write_text(first.replace(old, version) + "\n" + rest)
    path = root / "publishing/curseforge/metadata.json"
    metadata = json.loads(path.read_text())
    metadata.update(version=version, display_name=f"EnglishLinks {version}",
                    upload_file=f"EnglishLinks-{version}.zip")
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    path = root / "publishing/curseforge/UPLOAD.md"
    path.write_text(path.read_text().replace(old, version))


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def prepare(root, run_number, run_id, source):
    if not re.fullmatch(r"[0-9]+", run_id) or not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Invalid GitHub run ID or source SHA")
    config = json.loads((root / ".github/release-version.json").read_text())
    version = version_for_run(config, run_number)
    tag = "v" + version
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Release preparation requires a clean working tree")
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/tags/" + tag],
                            cwd=root).returncode == 0
    if exists:
        # A retry must rebuild exactly the previously tagged release, not retag it.
        message = git(root, "show", "-s", "--format=%B", tag)
        if (git(root, "rev-parse", tag + "^1") != source
                or f"Release-Run-ID: {run_id}" not in message.splitlines()):
            raise ValueError(f"{tag} already belongs to another release; refusing to overwrite")
        subprocess.run(["git", "checkout", "--detach", tag], cwd=root, check=True)
        if f"## Version: {version}\n" not in (root / "EnglishLinks/EnglishLinks.toc").read_text():
            raise ValueError("Existing tag has the wrong addon version")
    else:
        if git(root, "rev-parse", "HEAD") != source:
            raise ValueError("HEAD is not the commit that triggered this run")
        stamp_version(root, version)
    return version, tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    version, tag = prepare(ROOT, args.run_number, args.run_id, args.source)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"version={version}\ntag={tag}\n")
    print(f"Release {version} from {args.source}")


if __name__ == "__main__":
    main()

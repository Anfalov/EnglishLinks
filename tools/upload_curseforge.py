#!/usr/bin/env python3
"""Upload an existing release ZIP to CurseForge; never build or modify it."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib import error, request
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def parse_blizzard_version(text, region):
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError("Blizzard returned an empty versions table")
    rows = csv.reader(lines, delimiter="|")
    fields = [field.split("!", 1)[0] for field in next(rows)]
    if not {"Region", "VersionsName", "BuildId"}.issubset(fields):
        raise ValueError("Blizzard versions table is missing required columns")
    matches = []
    for row in rows:
        if len(row) != len(fields):
            raise ValueError("Malformed Blizzard versions row")
        record = dict(zip(fields, row))
        if record["Region"] == region:
            full = record["VersionsName"]
            match = re.fullmatch(r"(\d+\.\d+\.\d+)\.(\d+)", full)
            if not match or match[2] != record["BuildId"]:
                raise ValueError("Invalid Blizzard version or inconsistent build ID")
            matches.append((match[1], full))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one Blizzard versions row for region {region}")
    return matches[0]


def current_game_version(source):
    product, region = source["product"], source["region"]
    if not isinstance(product, str) or not re.fullmatch(r"[a-z0-9_]+", product):
        raise ValueError("Invalid Blizzard product code")
    if region not in {"eu", "us", "kr", "tw", "cn"}:
        raise ValueError("Invalid Blizzard region")
    # This table includes all regions; select the configured row, not the newest globally.
    url = f"https://us.version.battle.net/v2/products/{product}/versions"
    req = request.Request(url, headers={"User-Agent": "EnglishLinks-release"})
    try:
        with request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8-sig")
    except (error.URLError, TimeoutError, OSError, UnicodeError):
        raise RuntimeError("Cannot obtain current Blizzard version; upload stopped before sending to CurseForge") from None
    version, full = parse_blizzard_version(text, region)
    print(f"Blizzard {product} ({region}): {full}; CurseForge gameVersionNames: [{version}]")
    return version


def release_notes(text, version):
    match = re.search(r"^## " + re.escape(version) + r"(?:\s|$)[^\n]*\n(.*?)(?=^## |\Z)",
                      text, re.M | re.S)
    return match.group(1).strip() if match else f"English Links {version}: maintenance and name database updates."


def prepare_upload(root, archive, version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected a stable major.minor.patch release")
    config = json.loads((root / "publishing/curseforge/metadata.json").read_text())
    project_id = config["project_id"]
    if type(project_id) is not int or project_id <= 0:
        raise ValueError("Invalid CurseForge project_id")
    if archive.name != f"EnglishLinks-{version}.zip":
        raise ValueError("ZIP filename does not match release version")
    with ZipFile(archive) as package:
        toc = package.read("EnglishLinks/EnglishLinks.toc").decode()
        lua = package.read("EnglishLinks/EnglishLinks.lua").decode()
        if f"## Version: {version}\n" not in toc or f'local VERSION = "{version}"' not in lua:
            raise ValueError("ZIP runtime version does not match release")
    game_version = current_game_version(config["game_version_source"])
    changelog = (root / "publishing/curseforge/CHANGELOG.md").read_text()
    metadata = {
        "displayName": f"English Links {version}",
        "releaseType": "release",
        "gameVersionNames": [game_version],
        "changelogType": "markdown",
        "changelog": release_notes(changelog, version),
    }
    return project_id, metadata


def multipart(metadata, filename, data):
    boundary = "EnglishLinks-" + uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n'
        'Content-Type: application/json\r\n\r\n'
    ).encode() + json.dumps(metadata).encode() + (
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        'Content-Type: application/zip\r\n\r\n'
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the API credential to another endpoint.
        return None


def upload(project_id, metadata, archive, token):
    body, content_type = multipart(metadata, archive.name, archive.read_bytes())
    req = request.Request(
        f"https://wow.curseforge.com/api/projects/{project_id}/upload-file",
        data=body, method="POST",
        headers={"X-Api-Token": token, "Content-Type": content_type,
                 "Accept": "application/json", "User-Agent": "EnglishLinks-release"})
    # No automatic POST retry: a timeout may occur after the file was accepted.
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=120) as response:
            result = json.load(response)
    except error.HTTPError as exc:
        raise RuntimeError(f"CurseForge returned HTTP {exc.code}; check project access/token and CurseForge Files before retrying") from None
    except (error.URLError, TimeoutError, OSError, ValueError):
        raise RuntimeError("Upload outcome is unknown; check CurseForge Files before retrying") from None
    if not isinstance(result, dict) or type(result.get("id")) is not int or result["id"] <= 0:
        raise RuntimeError("No file ID returned; check CurseForge Files before retrying")
    return result["id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    project_id, metadata = prepare_upload(ROOT, args.zip, args.version)
    digest = hashlib.sha256(args.zip.read_bytes()).hexdigest()
    print(f"Project {project_id}; {args.zip.name}; SHA-256 {digest}")
    if args.dry_run:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return
    token = os.environ.get("CF_API_TOKEN", "").strip()
    if not token:
        raise ValueError("Add the CF_API_TOKEN repository secret in GitHub Actions settings")
    file_id = upload(project_id, metadata, args.zip, token)
    message = f"CurseForge accepted {args.zip.name}; file ID: {file_id}. Approval/publication is handled by CurseForge."
    print(message)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as out:
            out.write(message + "\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

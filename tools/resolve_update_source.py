#!/usr/bin/env python3
"""Resolve a fresh main snapshot, or reuse this workflow run's published result."""
import argparse
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def has_marker(root, commit, marker):
    return marker in git(root, 'show', '-s', '--format=%B', commit).splitlines()


def is_ancestor(root, ancestor, descendant):
    return subprocess.run(['git', 'merge-base', '--is-ancestor', ancestor, descendant],
                          cwd=root, check=False).returncode == 0


def matching_commits(root, revision, marker, tags=False):
    args = ['log', revision]
    if tags:
        args.append('--no-walk')
    candidates = git(root, *args, '--format=%H', '--fixed-strings', '--grep=' + marker)
    return [sha for sha in candidates.splitlines() if has_marker(root, sha, marker)]


def resolve(root, source, run_id):
    if not re.fullmatch(r'[0-9]+', run_id):
        raise ValueError('Invalid GitHub run ID')
    if source and not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('source_sha must be a full commit SHA')
    main = git(root, 'rev-parse', 'origin/main')
    update_marker = 'Update-Run-ID: ' + run_id
    releases = matching_commits(root, '--tags', 'Release-Run-ID: ' + run_id, tags=True)
    updates = matching_commits(root, 'origin/main', update_marker)
    if len(releases) > 1 or len(updates) > 1:
        raise ValueError('Multiple saved results for this run; refusing to choose one')
    # Re-run all jobs must keep the exact tagged source, even if sources or main
    # have changed since the first attempt. A pushed update is also a checkpoint.
    saved = git(root, 'rev-parse', releases[0] + '^1') if releases else (updates[0] if updates else '')
    if saved:
        changed = has_marker(root, saved, update_marker)
        original = git(root, 'rev-parse', saved + '^1') if changed else saved
        if source and original != source:
            raise ValueError('Saved result does not belong to the requested source')
        if not is_ancestor(root, saved, main):
            raise ValueError('Saved update is no longer in main')
        return {'source_sha': saved, 'prepared': True, 'changed': changed}
    source = source or main
    if source != main:
        raise ValueError('main advanced before preparation; start a new run from current main')
    return {'source_sha': source, 'prepared': False, 'changed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    result = resolve(ROOT, args.source, args.run_id)
    lines = [f'{key}={str(value).lower() if isinstance(value, bool) else value}'
             for key, value in result.items()]
    print('\n'.join(lines))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()

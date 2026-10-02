#!/usr/bin/env bash
set -euo pipefail

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git checkout -B autoupdate
git add EnglishLinks/NameData.lua data/auto-updates data/source-registry.json
git commit -m 'Update addon names' -m "Update-Run-ID: $GITHUB_RUN_ID"
previous=$(git ls-remote --heads origin autoupdate | cut -f1)
git push --force-with-lease="refs/heads/autoupdate:$previous" origin HEAD:refs/heads/autoupdate
# A concurrent main commit must be kept, even if this leaves the update on its
# service branch. A new updater run can start from the newer main.
git push origin HEAD:refs/heads/main
echo "sha=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"
git fetch origin develop
if git merge-base --is-ancestor origin/develop HEAD; then
    git push origin HEAD:refs/heads/develop || echo '::notice::develop advanced; left unchanged'
else
    echo '::notice::develop contains independent work; merge main before further development'
fi

#!/usr/bin/env bash
# Keep the retry queue across both workflows, including no-change runs.
set -euo pipefail
ref=refs/heads/quest-scan-state
file="${RUNNER_TEMP:?}/quest-pending.json"
basefile="$RUNNER_TEMP/quest-state-base"
case "$1" in
  load)
    remote=$(git ls-remote --heads origin "$ref")
    base=""
    if [[ -n "$remote" ]]; then
      git fetch --no-tags origin "$ref"
      base=$(git rev-parse FETCH_HEAD)
      git show "$base:pending.json" > "$file"
    else
      echo '[]' > "$file"
    fi
    echo "$base" > "$basefile"
    ;;
  save)
    base=$(cat "$basefile")
    blob=$(git hash-object -w "$file")
    parents=()
    if [[ -n "$base" ]]; then
      [[ $(git rev-parse "$base:pending.json") != "$blob" ]] || exit 0
      parents=(-p "$base")
    elif [[ $(cat "$file") == '[]' ]]; then
      exit 0
    fi
    tree=$(printf '100644 blob %s\tpending.json\n' "$blob" | git mktree)
    sha=$(git -c user.name=github-actions -c user.email=41898282+github-actions[bot]@users.noreply.github.com commit-tree "$tree" "${parents[@]}" -m 'Record pending Forever catalog IDs')
    git push origin "$sha:$ref"
    ;;
  *) exit 2 ;;
esac

# Implementation — EnglishLinks

## Runtime

- `NameData.lua`: prepared ID/name dictionaries, bonus suffixes and signed random
  properties. No source merging, timestamps or spell-to-profession table.
- `LinkText.lua`: pure hyperlink parser and label replacement. Payload, color and
  surrounding text are preserved; UTF-8 cursor positions are remapped.
- `Resolver.lua`: typed IDs, manual overrides, database lookup, recipe names from
  spell IDs, companion names from species IDs, generic map-pin label. Unknown or
  conflicting item suffixes preserve the original label. No client name learning.
- `EnglishLinks.lua`: hooks chat edit boxes while preserving normal insertion,
  focus checks, recursion guards and client length limits.

## Sources and updates

`tools/update_names.py` reads the installed dictionary, retrieves Wowhead Forever
and supplemental sources, and merges changes through `tools/name_data.py`.
Wowhead may add or rename; supplements may only add. Missing IDs are retained.
Downloaded JavaScript/Lua is parsed as data, never executed.
`tools/data_format.py` supplies validation and Lua 5.1 serialization helpers.

Wago importers/CSVs, QuestV2 coverage checks and unused relation/map datasets
have been removed. Old generated source packs are no longer test dependencies.
Saved Wowhead/community snapshots retain their provenance and hashes; historical
check reports describe the sources used at that time.

PetScout versions are discovered on CurseForge, archives are downloaded from
ForgeCDN, and only species names in `data/locations.lua` are imported. When
fresh discovery/download fails, the pinned ZIP can still be used with an explicit
fallback status and checksum validation.

The independent updater runs Monday/Thursday at 04:00 UTC or manually.
See [AUTO-UPDATE.md](AUTO-UPDATE.md) for publishing and concurrency rules.
Release only stamps the version and packages prepared files; no source comparison.

## Validation

`python tests/run_tests.py` covers source parsing, merge priority, unavailable
sources, no-op updates, Lua dictionary roundtrip, actual prepared addon loading,
link payloads, overrides, item variants, recipes, pets, cursors and UI hooks.
Git publishing tests exercise concurrent pushes and branch synchronization.

Offline tests do not establish server acceptance, recipient display, combat taint
behavior or compatibility with other addons. Recipes and basic item links were
previously confirmed in the client; this change has no new live-client test.

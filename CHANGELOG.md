# Changelog

## 0.6.3 — 2026-10-02

- Refresh English names after WoW Forever build 1.60.1.70170: add 40 items,
  44 spells, 81 quests and 23 random-property IDs.
- Update 48 item names, 24 spell names, 7 achievement names and one mount name.
- Keep previously known names when absent from the latest source snapshot.
- Remove version numbers from README headings.
- Wago exports for 70170 were unavailable; fallback CSVs remain from 70124.
  Offline checks passed; testing in the game client remains pending.

## 0.6.1 — 2026-10-01

- Translate 2,039 signed random-property IDs from Wowhead Forever (2,012
  positive, 27 negative; 46 distinct suffix names).
- Support rand and bonus IDs together without duplicating matching suffixes.
  Unknown IDs, malformed fields and conflicting suffixes keep the original label.
- Preserve payload, item variant, color, surrounding text and cursor position.
- Archive the Forever gear-planner response and tooltip evidence with hashes;
  add reproducible builds and regression checks for all shipped rand IDs.
- Offline and Wowhead-response verification passed; live-client testing remains pending.

## 0.6.0 — 2026-10-01

- Wowhead Forever is the primary source for names; all other sources fill gaps.
- QuestV2 now checks coverage only. No names are discarded by this reference.
- Includes 24,062 items, 31,795 spells, 5,250 quests, 154 skills, 434 achievements,
  9 currencies, 113 companion species and 217 summon-spell mount names.
- Translates 345 known item bonuses with 50 distinct English suffixes. Unknown
  bonuses and legacy random-property/suffix IDs preserve the original label.
- Map pins use Map Pin Location, retaining the atlas icon and coordinate payload.
  Removed the unnecessary UiMap name dictionary.
- Archived Wowhead source snapshots and added deterministic import/regression tests.

New suffix/map-pin behavior is verified offline, not yet in the live client.
Target: WoW Forever 1.60.1, Interface 16001.

## 0.5.0 — 2026-10-01

- Fixed translated profession recipe links by using the English recipe name
  without the profession prefix. The original recipe ID, link type and color
  are preserved. The change was confirmed in-game by the user on WoW Forever.
- Added an original EnglishLinks icon and an in-game screenshot.
- Prepared the CurseForge description, release notes and publication assets.
- Kept bundled English names, per-link-type controls and manual overrides.
  No client-side name collection or additional addon dependencies are required.

### Data included

24,020 item names; 31,703 spell names; 4,276 quest titles; 154 skill names;
433 achievement/statistic names; 5 currency names; 112 companion species names;
60 map names. Coverage is incomplete; unknown names keep their original labels.

### Known limitations

- Random-affix items retain their original labels.
- Companion links can fail to send because of game-side behavior also observed
  with untranslated links.
- This release targets WoW Forever 1.60.1 (Interface 16001). Compatibility with
  Retail and other Classic editions is not claimed.

## Earlier development

0.4.4-alpha.1 tested recipe-only English labels. The 0.4.3 approach that appended
an English annotation to a localized recipe link was rejected and reverted.
See [the decision log](docs/DECISIONS.md) for the development history.

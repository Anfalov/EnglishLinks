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

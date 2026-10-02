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

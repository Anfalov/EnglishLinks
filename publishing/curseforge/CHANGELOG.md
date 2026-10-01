## 0.6.1 — 2026-10-01

- Translate 2,039 signed random-property IDs from Wowhead Forever (2,012
  positive, 27 negative; 46 distinct suffix names).
- Support rand and bonus IDs together without duplicating matching suffixes.
  Unknown IDs, malformed fields and conflicting suffixes keep the original label.
- Preserve payload, item variant, color, surrounding text and cursor position.
- Archive the Forever gear-planner response and tooltip evidence with hashes;
  add reproducible builds and regression checks for all shipped rand IDs.
- Offline and Wowhead-response verification passed; live-client testing remains pending.

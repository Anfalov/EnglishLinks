# Changelog

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

# Implementation — EnglishLinks 0.4.2

## Primary sources inspected

- Client UI: https://github.com/Gethe/wow-ui-source/tree/forever
  pinned commit `bd2470aed543f72697a044e989285b6c83e63f73`.
- Table definitions: https://github.com/wowdev/WoWDBDefs/tree/master/definitions
  inspected for the tables listed in DATA-SOURCES.md. Actual input headers are
  validated; no CSV positional indexing or guessed cross-table IDs.

Relevant client files under `Interface/AddOns/`:
`Blizzard_ChatFrameBase/Mainline/ChatFrameUtilOverrides.lua`,
`Blizzard_ChatFrameBase/Shared/ChatFrameUtil.lua`,
`Blizzard_ChatFrameBase/Shared/ChatFrameEditBox.lua`,
`Blizzard_UIPanels_Game/Mainline/ItemRefHandlers.lua`,
`Blizzard_SharedXML/LinkUtil.lua`,
`Blizzard_PlayerSpells/ClassTalents/Blizzard_ClassTalentsFrame.lua`,
`Blizzard_APIDocumentationGenerated/QuestLogDocumentation.lua`,
`Blizzard_APIDocumentationGenerated/TradeSkillUIDocumentation.lua`.

The inspected UI commit predates data build 70009; native validation against the
installed client remains necessary. Inherited formats are optional capabilities,
not evidence that every corresponding gameplay feature exists in Forever.

## Structure and invariants

- `LinkText.lua`: pure parser, replacement of plain or bracketed labels only;
  payload, color and surrounding text preserved byte-for-byte. UTF-8 byte cursor
  remapping; escaped pipes and decorated labels remain unchanged. Legacy pure
  item API retained for regression tests.
- `Resolver.lua`: whitelist of typed payloads, disjoint ID namespaces, override →
  database. No client name learning or title requests. Old saved learned data is ignored.
  Journal, talentbuild and instancelock adapters and their dataset imports are removed.
  Their saved settings, overrides and missing IDs are cleaned on load.
  Legacy talent IDs are resolved through explicit Talent-to-Spell relations.
  Forever nonbattlepet links resolve species IDs through companion.
  Battlepet/battlePetAbil formats are unsupported and unchanged; no pet API is called. Items with a nonzero random-affix field are left
  entirely unchanged; no affix database adapter is shipped. Rank suffixes are retained when
  recognizable. Player/service/custom hyperlink types are not treated as game data.
- `QuestNames_enUS.lua`: offline title dictionary. `build_quests.py` parses pinned
  source snapshots as text, checks SHA-256, filters IDs against QuestV2, removes
  Completao's chain-step display annotations, and records per-ID provenance.
  No external Lua is executed. Source conflicts are reported, never merged silently.
- `EnglishLinks.lua`: instance `OnTextChanged` hooks on discovered chat edit boxes;
  post-hooks on activation/temporary window creation. Blizzard InsertLink is not
  replaced: macro/profession-search/auction workflows are not intercepted globally.
  Focus, secret values, recursion, raw byte/character limits checked before writes.
- `build_packs.py`: strict CSV schemas and exact declared Forever build; relational
  joins, duplicate/conflict checks, provenance hashes, atomic output. Ambiguous
  spell-to-profession relations are omitted. Empty/unsupported imports cannot
  silently overwrite an output. Locale must be chosen correctly at export.

## Data shipped and gaps

All six user-provided CSVs are for Forever 1.60.1.70124 / enUS and are preserved
unchanged in `data/`. ItemSparse contains 19,224 names, identical by ID/name to the
previous 70009 export; the current source hash and build metadata were regenerated.
SpellName contains 31,716 rows / 31,703 nonempty names. SkillLine contains 154 skill
names (not only professions). Achievement contains 433 achievement/statistic names.
SkillLineAbility supplies unambiguous spell-to-skill relations. QuestV2 supplies
6,605 IDs, no titles. Community sources supply 4,276 titles: 3,535 inherited
Classic names, 720 from QuestieDB Forever additions and 21 from two other sources.
See QUEST-SOURCES.md for the boundaries of this coverage. No test fixtures ship as data.

Removed features and rejected sources are recorded in DECISIONS.md.
Other optional datasets remain missing; coverage is reported per category.
The legacy Talent adapter does not establish compatibility of new Forever trees.

## Validation limits

Python unittest and Lua 5.1 via lupa cover schema joins, build rejection,
Lua generation roundtrip, labels, payloads, ranks, ID namespaces, overrides,
pet nicknames, UTF-8 cursor, UI hook simulation, caps, secrets and full item parity.
Quest tests cover source checksums, source priority/conflicts, ID filtering and
annotation removal. Integration tests reject any quest API access and verify
old learned data is ignored in English as well as Russian clients.
User confirmed item behavior in game. The new offline quest dictionary has not
been tested in the live client. Mocks do not establish server acceptance/recipient
display, combat taint behavior or compatibility with other addons.

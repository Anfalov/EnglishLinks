# Wowhead Forever: primary name source

Effective in 0.6.0. This is the source-of-truth policy requested by the
project owner: observed Wowhead Forever names win every built-in name conflict;
other pinned sources only fill missing IDs. Manual user overrides remain first.
Missing from Wowhead does not mean deleted from the game.

## Reproducible inputs

`data/wowhead-sources/snapshot.zip` retains the raw downloaded responses.
`manifest.json` records every source URL, parser, ID bounds and SHA-256, plus
retrieval timestamps when they were recorded. Unknown exact times are null.
The current snapshot was refreshed on 2026-10-02; ZIP timestamps are deterministic,
not retrieval times. Wowhead's exact client-data build is unknown.

`tools/build_wowhead.py` verifies saved archives and parses data literals without
executing downloaded code. Its optional offline output goes to `dist/`.
The installed addon loads `EnglishLinks/NameData.lua`; `tools/update_names.py`
updates that dictionary incrementally. Wowhead replaces changed names;
supplemental sources fill missing IDs only.

Item, quest and spell lists were partitioned over nonoverlapping inclusive ID
ranges covering 0..2147483647. The importer rejects gaps, overlap, truncated
lists and IDs outside requested bounds. This enumerates the acquired public
lists, not every hidden record in Wowhead. Existing item IDs omitted from lists
were checked through the public Forever Gatherer endpoint (50 responses per
request observed); four omitted spells were recovered from individual pages.
Small categories use embedded list JSON; companions use species IDs rather than
outer NPC keys. Mount keys are summon-spell IDs. No zone AreaID/UiMapID mapping
is inferred or required.

The prepared dictionary contains 5,331 quest names: 5,287 from the saved
Wowhead snapshots and 44 supplemental titles. No reference-ID coverage check
is performed.

## Item suffixes

The public Forever `data/item-bonuses` response maps bonus IDs to effects, and
`wow.item.bonusNameDescriptions` maps description IDs to English text.
Wowhead's own core.js defines effect 5 as `EFFECT_TYPE_NAME_SUFFIX`; effect 4 is
`EFFECT_TYPE_TAG_DESCRIPTION` (a tooltip tag, not an item-name prefix).
The snapshot supplies 345 suffix-bearing bonuses, 50 distinct suffix strings,
and 20 known bonuses without suffixes.

Resolver splits an item payload including the leading `item` token:
field 8 is the signed random-property ID; field 14 is bonus count; fields 15 onward
are bonus IDs. Known effect-5 text is appended to the English base item name.
Example: item 10378 + bonus 12722 → Commander's Armor of the Bear.
This matches Wowhead's actual tooltip response saved in bonus-example.json.
Unknown/malformed IDs and competing suffixes preserve the complete original
label. Random-property IDs are never assumed to equal bonus/description IDs.
New behavior is tested offline and awaits a real client link.

### Signed random properties (`rand`), added in 0.6.1

The earlier 0.6.0 investigation was incomplete. The Forever tooltip service
also resolves random-property names, and the Forever gear-planner response
contains a complete `wow.gearPlanner.classicplus.randomEnchant` table.
Its internal namespace is `classicplus`, but the source URL is `/forever/`.
The archived response supplies 2,062 IDs: 2,033 positive and 29 negative,
with 53 distinct suffix strings. All entries are retained, including unusual
source labels. No Classic/Retail names or IDs are guessed or substituted.

`tools/build_random_affixes.py` verifies archive/response SHA-256 hashes,
extracts only JSON literals without executing downloaded code, validates signed
IDs and safe names, checks saved tooltip evidence, and generates
an optional offline pack in `dist/`. The separate raw snapshot and exact
retrieval completion timestamps are in `data/random-affix-sources`.
Run `python tools/build_random_affixes.py` for an offline rebuild.

Verified tooltip examples:
- item 6614 + rand 763 or -9: Sage's Cloak of the Owl.
- item 10378 + rand 1215 or -68: Commander's Armor of the Bear.
- rand -7 is absent from this Forever table and its saved tooltip leaves the
  base name unchanged. A generic Wowhead guide mentioning -7 does not establish
  a Forever mapping, so the addon keeps such an unknown link unchanged.

The sign is significant. A known nonzero rand ID now supplies an English suffix
instead of preventing translation. If both rand and bonus IDs supply the same
suffix it is appended once; different suffixes, unknown IDs or malformed fields
preserve the original label. Payload, including the variant ID and unique ID,
color and surrounding text remain unchanged; cursor offsets are adjusted.
The same behavior works for shorter links without a bonus-count field.
Direct ItemRandomProperties/ItemRandomSuffix DB2 exports are not needed for this
implementation: the signed mapping comes from the verified Wowhead response.
These response checks do not establish which variants the live client emits.

## Map pins

The inspected Forever UI snapshot is Gethe/wow-ui-source commit
`966519cf0ad2c10301ea011a88c14b25697c9687`.
`Blizzard_SharedMapDataProviders/WaypointLocationDataProvider.lua` inserts
`C_Map.GetUserWaypointHyperlink()` on modified click. UiMapID identifies the
map that coordinates belong to. It does not imply a zone name in visible text.
The standard English label is `Map Pin Location`; the native
`Waypoint-MapPin-ChatIcon` atlas escape is retained. UiMap names are no longer
needed or shipped. The original worldmap payload and coordinates are unchanged.

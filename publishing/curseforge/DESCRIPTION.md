# EnglishLinks

**Keep your game in your language. Share links with English names.**

EnglishLinks replaces the names inside game links as you insert them into chat.
Other players receive English link labels, while your interface and the tooltips
you open stay in your client language. It is built for **WoW Forever**.

![English links in chat with a Russian WoW Forever interface](https://raw.githubusercontent.com/Anfalov/EnglishLinks/main/docs/images/english-links-in-game.jpg)

*English item, ability and recipe links in chat; Fireball and The Restless Dead
in the chat input. The open Mana Well recipe tooltip is still in Russian.*

## How it works

Open chat and Shift-click a supported item, spell, quest or recipe as usual.
EnglishLinks substitutes its English name before you press Enter. The link
keeps its original ID, parameters and color, so clicking it opens the original
game content. Recipients do not need EnglishLinks installed.

English names come bundled with the addon. There is no collection step, language
switch or waiting for a name scan, and no other addon is required.

## Features

- English labels for items, spells, quests and profession recipes.
- Additional name coverage for skills, achievements, currencies, companion
  species and map pins; mount links can use summon-spell names.
- Profession recipe links use the English recipe name, such as **[Mana Well]**,
  while retaining their original recipe link.
- Per-link-type switches and manual name overrides.
- Coverage information and a list of missing IDs to help report gaps.
- Your surrounding message text is preserved. Messages are sent only when you
  send them; incoming chat and the rest of the interface are not translated.

## Getting started

Install EnglishLinks for the **WoW Forever** client. For manual installation,
extract the `EnglishLinks` folder into that client's `Interface/AddOns` folder.
The final path should be `Interface/AddOns/EnglishLinks/EnglishLinks.toc`.

Start the game, open chat and insert a link. Use `/el status` to check the addon
and `/el coverage` to see which name packs are installed.

## Useful commands

- `/el on` and `/el off` — enable or disable translation.
- `/el status` — display version and status.
- `/el coverage` — show bundled name counts.
- `/el type enchant off` — disable recipe translation; use `on` to re-enable it.
- `/el missing` — show recorded missing IDs.
- `/el set quest 7 Kobold Camp Cleanup` — set a manual English name.
- `/el unset quest 7` — remove that override.

Disabling translation does not undo links already changed in the chat input.
Clear and reinsert a link to use its original name.

## Coverage and compatibility

Version 0.5.0 includes **24,020 item names**, **31,703 spell names** and
**4,276 quest titles**, plus smaller supplementary name packs. Coverage is
incomplete: missing names and unsupported links keep their original labels.
Items with random affixes also keep their original labels.

The target is **WoW Forever 1.60.1**. Retail and other Classic editions have not
been validated. Companion links may fail to send even without translation;
EnglishLinks cannot fix that game behavior. Battle-pet links, dungeon-journal
links, talent-build links and instance-lockout links are not supported.

## Credits and support

Name sources include WoW client tables through Wago, QuestieDB, Everything Quests,
Completao, ElliotWood/Forever, PetScout Forever and TheWoWDB. Their attribution
and applicable license notices are included with the addon. World of Warcraft
and its game content belong to Blizzard Entertainment or its licensors.

EnglishLinks code is released under **GNU GPL v3**.

[Report a bug](https://github.com/Anfalov/EnglishLinks/issues) ·
[Source code and data provenance](https://github.com/Anfalov/EnglishLinks)

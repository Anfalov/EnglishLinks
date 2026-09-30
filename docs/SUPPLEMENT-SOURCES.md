# Дополнения Forever — EnglishLinks 0.4.3

Проверено 30 сентября 2026. Полнота базы не заявляется.

## Предметы

Исходный ItemSparse 1.60.1.70124 / enUS содержит 19 224 названия.
Это вся наша выгрузка таблицы, а не все предметы игры. Например, независимая
[квитанция выгрузки](https://wowfwiki.com/forever-assets/datamine-archive-70124-coverage.json)
показывает 31 818 строк Item и 19 224 ItemSparse. Item не содержит готовых
названий: разность этих чисел нельзя объявлять числом доступных предметов.

Дополнительные источники, в порядке приоритета после Wago:

| Источник | Имен просмотрено | Добавлено |
| --- | ---: | ---: |
| QuestieDB, сгенерированные дополнения Forever | 8 151 | 1 127 |
| Wowhead Forever gear planner, снимок ElliotWood/Forever | 11 269 | 3 669 |
| Итого новых названий | | 4 796 |

Всего в аддоне 24 020 названий. Ни один пересекающийся ID не имел другого
названия. Старые имена Wago не перезаписываются; ручные overrides выше всех баз.

QuestieDB закреплён на `f521c36eb72a57d7f205a61ee212ad0ca9f51ed9`:
`src/corrections/Forever/generated/foreverBaseItem.lua`.
В нём 6 209 присваиваний name (680 новых для нас) и подписанные комментарии
с ID, названием и ссылкой именно `wowhead.com/forever/item=...`. Комментарии
дают ещё 447 названий. Их ID и явные имена проверяются на согласованность.
Полный унаследованный Classic foreverItemDB.lua в эту поставку не импортирован.
[Политика источника](https://github.com/Questie/QuestieDB/blob/f521c36eb72a57d7f205a61ee212ad0ca9f51ed9/docs/forever-delta-base.md).

Снимок gear planner:
[ElliotWood/Forever](https://github.com/ElliotWood/Forever/blob/d91d4afe408363db83a0d35ea444e696092e9a87/assets/db_inputs/wowhead_forever_gearplanner.txt),
коммит `d91d4afe408363db83a0d35ea444e696092e9a87`.
Читается только `wow.gearPlanner.classicplus.item`; каждая запись имеет
`versionNum=16001`. JavaScript не исполняется. Это снимок базы сообщества для
Forever, а не объявленная выгрузка DB2 точной сборки 70124. Статистика,
источники добычи и цены из него не используются. Проект основан на
[wowsims/classic](https://github.com/wowsims/classic), MIT notice сохранён.

SHA-256 исходников: `data/supplement-sources/manifest.json`. Git blob-хеши
обоих файлов были сверены с деревьями закреплённых коммитов. Для каждого
добавленного имени источник записан в `data/ItemNames.community.csv`.

## Валюты

Добавлены пять фактических пар ID/имя из индивидуальных страниц
[TheWoWDB Forever](https://thewowdb.com/wow-forever/currencies/), помеченных
сборкой 1.60.1.70124: 515 Darkmoon Prize Ticket, 1792 Honor Points,
3402 Merchant's Favor, 3468 Rank Points, 3469 Tarnished Undermine Real.
URL каждой записи сохранён в `data/supplement-sources/currencies.json`.
Это выборка названий, не полная копия CurrencyTypes и не утверждение, что
каждая валюта доступна игроку в текущей фазе беты.

## Что подтверждено для форматов ссылок

Изучен исходный интерфейс Blizzard, Forever commit
`bd2470aed543f72697a044e989285b6c83e63f73` в
[Gethe/wow-ui-source](https://github.com/Gethe/wow-ui-source/tree/bd2470aed543f72697a044e989285b6c83e63f73/Interface/AddOns).

| Категория | Результат |
| --- | --- |
| Таланты | SharedTalentUI вставляет C_Spell.GetSpellLink. Такие ссылки уже работают через spell. Пустая talent относилась к старому формату, а не ко всем талантам. |
| Транспорт | MountJournalDocumentation: GetMountLink принимает spellID. DressUpFrames разрешает mount: через GetMountFromSpell. Исправлен поиск по ID заклинания; имена берутся из spell, если нет отдельного mount. Импорт Mount теперь индексируется SourceSpellID. |
| Валюты | TokenUI/Camelot вставляет GetCurrencyListLink. Категория актуальна. |
| Питомцы-компаньоны | Classic PetCollection имеет отдельный GetNonBattlePetLinkByIndex. Из PetScout добавлены 112 имён по speciesID. Пользовательская диагностика 2026-10-01 подтвердила nonbattlepet:5005. С 0.4.1 этот формат разрешается через companion; battlepet и battlePetAbil удалены из поддерживаемых форматов. |
| Боевые питомцы / petability | Наличие BattlePetSpecies в данных не доказывает наличие боёв питомцев. PetScout Forever явно описывает коллекцию без боёв; отдельная база боевых способностей здесь не нужна. Способности питомца охотника как spell уже обрабатываются. |
| Метки карты | Для worldmap добавлены 60 названий UiMap из PetScout. |

[PetScout Forever](https://www.curseforge.com/wow/addons/petscout-forever)
указывает 112 видов для старой сборки 69913. В архиве версии 0.1.1 найден
встроенный fallback английских имён: data/locations.lua (112 speciesID)
и data/zones.lua (60 UiMapID). Встроены только ID/имя; клиентский сбор,
координаты и код PetScout не подключаются. Снимки этих файлов и лицензия MIT
сохранены. Исходная сборка остаётся 69913, переименования более новой сборки
не проверены. Указанный GitHub-репозиторий недоступен (404 при проверке),
но официальный архив CurseForge 8940612 скачан с его публичного CDN.
Прямые дополнительные CSV Wago в этой сессии вернули HTTP 403; это не
доказательство отсутствия таблиц. Сведения с сайтов не объявлены выгрузками.

Сбор названий клиентом не возвращён. Неизвестная ссылка остаётся исходной.
Клички питомцев и имена игроков не переводятся. Проверки выполнялись вне игры;
журнал транспорта и валюты необходимо проверить в реальном клиенте.
Исходный формат питомца подтверждён пользователем; исправленный перевод
проверен тестом вставки в поле чата, но ещё не подтверждён после установки в игре.

## Пересборка

`python tools/build_supplements.py` создаёт SupplementNames_enUS.lua,
ItemNames.community.csv и supplement-report.json. Оригинальный ItemNames_enUS.lua
остаётся побайтно прежним. В TOC дополнительный пакет загружается после Resolver.

В 0.4.2 удалены journal, talentbuild и instancelock, связанные категории и импорт
их таблиц. Они больше не входят в список недостающих данных; история — DECISIONS.md.

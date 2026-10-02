# Данные аддона

Рабочая база — `EnglishLinks/NameData.lua`. В ней находятся английские названия,
бонусные окончания и знаковые ID случайных свойств предметов.

Основной источник — Wowhead Forever. QuestieDB, Everything Quests, Completao,
ElliotWood/Forever, TheWoWDB и PetScout Forever дополняют отсутствующие ID.

Wago, его CSV и сборщики удалены. Проверки полноты по QuestV2 нет.
Таблицы связей Spell → SkillLine и названий карт не используются и удалены.
Рецепты разрешаются по spell ID; метки карты используют `Map Pin Location`.

- [Автоматическое обновление](AUTO-UPDATE.md)
- [Адреса и происхождение источников](SOURCE-REGISTRY.md)
- [Wowhead и окончания предметов](WOWHEAD-SOURCES.md)
- [Источники заданий](QUEST-SOURCES.md)

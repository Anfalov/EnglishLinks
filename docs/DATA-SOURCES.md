# Данные Forever для EnglishLinks 0.4.3

Все ссылки ниже запрашивают **1.60.1.70124 / enUS**, как уже работающий ItemSparse.
Сохраняй скачанные файлы с исходными именами таблиц и присылай вместе.
Не выбирай Classic/Era или другую сборку вместо Forever.

Получены и встроены: **ItemSparse, SpellName, SkillLine, Achievement,
SkillLineAbility, QuestV2**. Исходные файлы сохранены в `data` без изменений.

Остальные исходные CSV ниже не получены. Однако часть названий уже добавлена
из общественных источников: пять валют, 112 видов питомцев и 60 карт; ссылки
маунтов используют spell ID. Обновлённый аудит: `SUPPLEMENT-SOURCES.md`.
Список ниже — справочник схем, а не перечень обязательных загрузок.
Не заменяй отсутствующие таблицы данными Classic/Era. Старый Talent нельзя считать
подтверждённым источником новых деревьев талантов Forever: его импорт предназначен
для старого формата ссылок. Отдельные таланты новых деревьев вставляются как spell и уже работают.
Обработчики journal, talentbuild и instancelock удалены в 0.4.2 вместе с импортом
ChrSpecialization, JournalInstance, JournalEncounter, JournalEncounterSection и Map.

| Скачать CSV | Назначение | Поле кроме ID |
| --- | --- | --- |
| [SpellName](https://wago.tools/db2/SpellName/csv?build=1.60.1.70124&locale=enUS) | Заклинания, способности, изготовление/чары | `Name_lang` |
| [SkillLine](https://wago.tools/db2/SkillLine/csv?build=1.60.1.70124&locale=enUS) | Профессии | `DisplayName_lang` |
| [Achievement](https://wago.tools/db2/Achievement/csv?build=1.60.1.70124&locale=enUS) | Достижения | `Title_lang` |
| [SkillLineAbility](https://wago.tools/db2/SkillLineAbility/csv?build=1.60.1.70124&locale=enUS) | Связь рецепта и профессии | `Spell + SkillLine` |
| [QuestV2](https://wago.tools/db2/QuestV2/csv?build=1.60.1.70124&locale=enUS) | ID для фильтрации базы заданий при сборке; НЕ названия | `ID` |
| [CurrencyTypes](https://wago.tools/db2/CurrencyTypes/csv?build=1.60.1.70124&locale=enUS) | Валюты | `Name_lang` |
| [Talent](https://wago.tools/db2/Talent/csv?build=1.60.1.70124&locale=enUS) | Таланты → заклинания | `SpellID или SpellRank_N` |
| [BattlePetSpecies](https://wago.tools/db2/BattlePetSpecies/csv?build=1.60.1.70124&locale=enUS) | Виды питомцев → существа | `CreatureID` |
| [Creature](https://wago.tools/db2/Creature/csv?build=1.60.1.70124&locale=enUS) | Названия видов питомцев | `Name_lang` |
| [Mount](https://wago.tools/db2/Mount/csv?build=1.60.1.70124&locale=enUS) | Прямые ссылки на транспорт | `Name_lang`, ключ `SourceSpellID` |
| [UiMap](https://wago.tools/db2/UiMap/csv?build=1.60.1.70124&locale=enUS) | Метки карты | `Name_lang` |

ItemSparse 1.60.1.70124 уже встроен и проверен, повторно присылать его не нужно.

Для питомцев BattlePetSpecies и Creature нужны вместе. Talent и SkillLineAbility
содержат связи, а не готовые имена: также нужны SpellName и SkillLine.

**Задания:** названия уже встроены из трёх общественных баз. QuestV2 служит
фильтром допустимых ID при сборке и не загружается в память аддона.
Источники, происхождение старых названий и порядок сборки: `QUEST-SOURCES.md`.
История отказа от клиентского сбора и двух недоступных таблиц: `DECISIONS.md`.

Если прямой CSV-адрес открывает страницу проверки, открой `https://wago.tools/db2`,
выбери таблицу, сборку 1.60.1.70124, локаль enUS и используй её экспорт CSV.
CSV не позволяет надёжно проверить локаль; выбирать английскую обязательно.
Порядок импорта описан в README.md.

Название клиентской таблицы BattlePetSpecies не означает наличие боёв питомцев.
Она может описывать виды компаньонов; в аддоне категория называется companion,
формат подтверждённой ссылки — nonbattlepet:speciesID.

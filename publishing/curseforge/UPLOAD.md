# Публикация EnglishLinks 0.6.2 на CurseForge

Подготовлена сборка 0.6.2; новые окончания и метки карты ещё не проверены в игре. Проект на CurseForge автоматически не создан.

## Поля проекта

| Поле | Значение |
| --- | --- |
| Name | EnglishLinks |
| Summary | Share game links with English names while keeping your WoW Forever client in your own language. |
| Game | World of Warcraft |
| Class | Addons |
| Main category | Chat & Communication |
| Project license | GNU General Public License version 3 (GPLv3) |
| Source | https://github.com/Anfalov/EnglishLinks |
| Issues | https://github.com/Anfalov/EnglishLinks/issues |
| Logo | englishlinks-icon.png — PNG, ровно 400×400 |
| Description | DESCRIPTION.md; для HTML-режима — DESCRIPTION.html |

Создание проекта: https://authors.curseforge.com/#/projects/create/choose-game

Английское описание уже включает скриншот через публичный URL GitHub.
Скопируй текст в соответствующий режим редактора (Markdown или HTML), затем
проверь предварительный просмотр. Если редактор принимает только визуальный
ввод, открой DESCRIPTION.html в браузере и скопируй отформатированное содержимое.
Для изображения можно также использовать кнопку вставки изображения с URL
из SCREENSHOT.txt или загрузить приложенный JPG.

## Файл аддона

| Поле | Значение |
| --- | --- |
| Upload file | EnglishLinks-0.6.2.zip |
| Display name | EnglishLinks 0.6.2 |
| Release type | Release |
| Game flavor | WoW Forever / Forever |
| Game version | 1.60.1 |
| Changelog | CHANGELOG.md из этого комплекта |
| Required dependencies | Нет |

Установочный ZIP содержит только папку EnglishLinks с кодом, базами, значком,
инструкциями и лицензиями. **EnglishLinks-0.6.2-CurseForge-kit.zip — комплект
для автора; не загружай его как файл аддона.**

Поддержку Retail, Era, TBC и других изданий не отмечать: они не проверены.
Номер 0.6.2 — версия аддона; 1.60.1 — версия игры.

## Галерея

Загрузи english-links-in-game.jpg. Заголовок и подпись готовы в SCREENSHOT.txt.
Оригинальный скриншот сохранён без ретуши. В README используется тот же файл.

## Что проверить перед отправкой

1. В описании видны скриншот, список поддерживаемых ссылок и команды.
2. Выбраны Forever и 1.60.1, а файл называется EnglishLinks-0.6.2.zip.
3. При ручной установке нет лишней внешней папки вокруг EnglishLinks.
4. После загрузки проекта и файла дождаться проверки модерацией CurseForge.

## Проверенные требования площадки

Проверено 1 октября 2026, Asia/Yekaterinburg. CurseForge требует английские
название/описание (переводы можно добавить после английского текста), аватар
400×400 и файл проекта для отправки на модерацию. PNG выбран вместо WebP.
Для источников и поддержки оставлены ссылки на репозиторий и issues;
сторонних ссылок скачивания аддона в описании нет.

- [Создание проекта](https://support.curseforge.com/support/solutions/articles/9000197241-creating-and-submitting-a-project)
- [Правила модерации](https://support.curseforge.com/support/solutions/articles/9000197279-moderation-policies)
- [Типы файлов](https://support.curseforge.com/support/solutions/articles/9000197242-file-types-and-additional-fields)

Собрать комплект заново из репозитория: `python3 tools/package_release.py`.

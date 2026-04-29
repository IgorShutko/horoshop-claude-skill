# Changelog

## [v1.0.0] — 2026-04-29

🎉 First public release.

### Added

- Скилл `horoshop-full-audit` для Claude Code: полный SEO-аудит магазина на Хорошопе через API
- Оркестратор `scripts/audit.py`:
  - Выгрузка каталога через `catalog/export` с пагинацией
  - Рекурсивная выгрузка всех категорий через `pages/export`
  - HTML-парсинг публичных страниц (главная, все категории, sample товаров)
  - Парсинг `sitemap.xml` и `robots.txt`
  - Генерация `REPORT.md` с разделением на ✅/🟢/🟡 секции
- 10 API-фиксов в `scripts/apply_fixes.py`:
  - `countdown` — обнуление истёкших таймеров акций
  - `mod-title` — заполнение названий модификаций из ключевых характеристик
  - `discount` — пересчёт скидки по `price`/`price_old`
  - `seo` — заполнение пустых SEO-полей с превью
  - `mpn` — генерация MPN по бренд-префиксу
  - `dup-desc` — уникализация дубликатов описаний
  - `installments` — включение оплаты частями
  - `sticker-sale` — добавление стикера «Распродажа»
  - `inline-styles` — очистка inline-стилей в описаниях
  - `cross-sell` — настройка accessories/alt_parent
- 4 справочника в `references/`:
  - `api_admin_setup.md` — инструкция создать API-юзера
  - `api_quickref.md` — справочник API endpoints и полей
  - `audit_checklist.md` — 18 проверок с обоснованиями
  - `fix_recipes.md` — рецепты каждого фикса
- Поддержка `--dry-run` и `--preview-only` для всех контентных фиксов
- Обработка кода 11 API (поле не в шаблоне) — с инструкцией где включить
- README на русском и украинском (`README.md`, `README.uk.md`)
- Sample отчёт в `examples/sample-REPORT.md`
- One-line installer (`install.sh`) + `.skill` package в релизах

[v1.0.0]: https://github.com/IgorShutko/horoshop-claude-skill/releases/tag/v1.0.0

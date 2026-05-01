---
name: horoshop-content-fill
description: Заполнение пустых полей карточек товаров в магазине на Хорошопе через API. Используй ВСЕГДА когда пользователь просит "заполнить пустые описания", "сгенерировать описания товаров", "дополнить карточки", "массово прописать short description / marketplace description", "найти товары с пустыми полями". Скилл сканирует каталог через `catalog/export`, находит товары с пустыми `description`, `short_description`, `marketplace_description`, готовит контекст для генерации, после одобрения применяет через `catalog/import`. НЕ путать с `horoshop-full-audit` — тот про SEO-баги (пустые seo_title, mod_title, discount), этот про **массовое наполнение основного контента**.
---

# Horoshop Content Fill

Массовое заполнение пустых полей карточек товара через API.

## Когда применять

- «Заполни пустые описания»
- «Сгенерируй описания товаров»
- «Дополни карточки на хорошопе»
- «Найди товары без description»
- «Прописать marketplace_description массово»

## Что заполняет

| Поле | Когда заполнять | Длина |
|---|---|---|
| `description.<lang>` | пусто или <200 симв | 800-1500 симв с h2/h3 |
| `short_description.<lang>` | пусто | 100-200 симв, plain text |
| `marketplace_description.<lang>` | пусто | 50-150 симв, plain text, для фидов |

**Не трогаем:**
- Поля которые уже заполнены и >минимума (не переписываем)
- `seo_title`/`seo_description`/`h1_title` — это в `horoshop-full-audit` (`--fix seo`)
- `mod_title` — это в `horoshop-full-audit` (`--fix mod-title`)
- `characteristics` — нельзя автогенерировать (это физические параметры товара)

## Pipeline

```
[1] Вводные: домен + креды (если auth не прошёл — инструкция создать API-юзера)
        ↓
[2] Сбор контекста про магазин:
    - Бренд / название
    - Категория товаров (текстиль / электроника / косметика / ...)
    - Тон (B2C разговорный / B2B формальный)
    - Целевая аудитория
        ↓
[3] Запуск find_gaps.py — сканирует каталог, формирует gaps.json
        ↓
[4] Claude (в основном чате) читает gaps.json + references/content_templates.md
    Генерирует тексты для каждого товара
    Сохраняет в proposed_content.json
        ↓
[5] apply_content.py --preview-only — показывает diff первых 3-5 товаров
        ↓
[6] После одобрения: apply_content.py — импорт через catalog/import пакетно
```

## Шаг 1 — Вводные

Спроси у пользователя:
1. **Домен** магазина
2. **Креды** API-юзера (если нет — инструкция создать как в `horoshop-full-audit/references/api_admin_setup.md`)
3. **Бренд / название магазина** — нужно для генерации (например «MyBrand»)
4. **Тон** — формальный или разговорный
5. **Особенности магазина** — что подчёркиваем (свой пошив, доставка 1 день, гарантия и т.д.)

## Шаг 2 — Auth check

Стандартно: POST `/api/auth/`. Если фейл — инструкция создать API-юзера.

## Шаг 3 — Поиск пустых полей

```bash
mkdir -p content_<domain>
cd content_<domain>
HOROSHOP_DOMAIN=<DOMAIN> HOROSHOP_LOGIN=<LOGIN> HOROSHOP_PASSWORD=<PASSWORD> \
  python3 ${SKILL_DIR}/scripts/find_gaps.py
```

Опции:
- `--from-file catalog.json` — читать каталог из локального файла (если уже выгружен)
- `--min-desc-len 200` — порог длины description чтобы считать «пусто-эквивалент» (default 200)
- `--field description,short_description,marketplace_description` — какие поля проверять (default все три)

Output:
- `catalog.json` — выгруженный каталог
- `gaps.json` — товары с пустыми полями + контекст

Скрипт также печатает сводку:
```
Главных товаров: 44
Пустых description: 12
Пустых short_description: 8
Пустых marketplace_description: 31

→ Всего товаров с пустыми полями: 35
→ gaps.json: <path>
```

## Шаг 4 — Генерация контента (Claude в основном чате)

Это **самый важный шаг**. Прочитай:
1. `gaps.json` — что нужно заполнить
2. `references/content_templates.md` — структура и требования
3. `references/prompt_recipes.md` — как генерировать (тон, паттерны, чего избегать)

Сгенерируй для каждого товара тексты на основе:
- `title` — название товара
- `characteristics` — заполненные характеристики
- `brand`, `category`, `price`
- `existing_description` — если есть (для подражания стилю)
- Контекст магазина от пользователя (бренд, тон, особенности)

Сохрани результат в `proposed_content.json`:
```json
[
  {
    "article": "1234",
    "description": "<p>...</p><h2>Особливості</h2>...",
    "short_description": "...",
    "marketplace_description": "..."
  }
]
```

**Важно:**
- Не выдумывай характеристики которые не указаны
- Не переписывай уже заполненные поля без явной просьбы
- Описания на украинском (или язык магазина) — соблюдай мультиязычность
- Без AI-стоп-слоп (см. `references/prompt_recipes.md` или подключай скилл `stop-slop`)

## Шаг 5 — Превью

```bash
python3 ${SKILL_DIR}/scripts/apply_content.py --preview-only
```

Показывает первые 3-5 товаров: текущее → новое. Пользователь смотрит, говорит «заходит» / «переделай».

Если не заходит — попроси пользователя сказать что не так (тон, длина, факты), скорректируй промпт, перегенерируй `proposed_content.json`, снова preview.

## Шаг 6 — Импорт

После одобрения:

```bash
python3 ${SKILL_DIR}/scripts/apply_content.py
```

Запросит подтверждение `(y/N)`, затем импортирует пакетно через `catalog/import` (батчи по 50). Лог сохраняется в `fix_content_<timestamp>.json`.

## Tone of voice

Лаконично, без воды. Spike-стиль. Цифры — главное.

## Reference files

- `references/content_templates.md` — структура полей (что должно быть в description, какая длина, что в short)
- `references/prompt_recipes.md` — паттерны генерации, чего избегать, тональность
- `references/horoshop_help.md` — выжимка из справки Хорошопа: текстовые поля карточки, что в `description` vs `short_description` vs `marketplace_description`, SEO шаблоны, code 11, Шаблон даних. **Цитируй её при превью/отчётах со ссылками на источник.**

## Что НЕ делать

- ❌ Не записывать через API без `--preview-only` сначала
- ❌ Не переписывать уже заполненные поля если пользователь явно не попросил
- ❌ Не выдумывать характеристики (материал, страна, размер) — только то, что в `characteristics`
- ❌ Не дублировать функционал `horoshop-full-audit` (пустые SEO-поля и mod_title — там)
- ❌ Не генерировать тексты с AI-стоп-слоп паттернами («буквально», «по сути», «при этом», «является» и т.д.)

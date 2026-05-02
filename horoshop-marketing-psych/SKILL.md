---
name: horoshop-marketing-psych
description: Применение психологических приёмов и поведенческих триггеров к ТЕКСТУ карточек товаров на Хорошопе для повышения конверсии. Используй ВСЕГДА когда пользователь просит "добавь маркетинг приёмы", "психологические триггеры в карточки", "переписать описания продающим стилем", "scarcity / social proof / anchoring к товарам". Скилл переписывает description / short_description / marketplace_description через `catalog/import` с превью. НЕ пишет icons[] — кастомные стикеры через API создать невозможно (только текстовые приёмы).
---

# Horoshop Marketing Psychology

Применение психо-приёмов к ТЕКСТУ карточек товаров для роста конверсии.

## Что делает (а что нет)

✅ **Делает:**
- Переписывает `description` через `catalog/import`
- Переписывает `short_description` через `catalog/import`
- Опционально — `marketplace_description`, `h1_title`
- Добавляет в текст элементы scarcity / social proof / anchoring / loss aversion / reciprocity / authority / commitment

❌ **Не делает:**
- Не пишет `icons[]` (стикеры) — кастомные стикеры **невозможно создать через API**, только в админке
- Не пишет `countdown_end_time` (через `horoshop-full-audit` или вручную)
- Не пишет `gifts[]` (требует существующих товаров-подарков)
- Не делает `price_old` / `discount` — это работа с прайс-листом

## 7 приёмов которые применяет (в тексте)

### 1. Scarcity (Дефицит)
- В description: «У наявності лишилось 3 одиниці — наступне постачання за 2 тижні»
- В short_description: «Останній розмір M»

### 2. Social proof (Соц. доказательство)
- В description: «Цей комплект обрали 247 покупців за останній місяць»
- В short_description: «Топ-3 у категорії "Постільна білизна"»

### 3. Anchoring (Якорь)
- В description: «**999 грн** ~~~~ → 599 грн. Економія 400 грн (40%)»
- Сравнение: «У конкурентів аналогічна якість від 800 грн»

### 4. Loss aversion (Страх потери)
- В description: «Не пропустіть знижку — після 31 грудня ціна повертається до базової 999 грн»

### 5. Reciprocity (Взаимность)
- В description: «До замовлення — безкоштовний наматрацник у подарунок (вартість 199 грн)»

### 6. Authority (Авторитет)
- В description: «Власне виробництво з 2015 року, сертифікат Oeko-Tex»

### 7. Commitment & consistency
- В короткому опису: «Оберіть розмір — побачите точну ціну»

## Pipeline

```
[1] find_targets.py — выгрузка каталога, выбор товаров для psych-обогащения
    Приоритет: товары группы A из ABC (если есть SALES_REPORT.md)
    Или: все товары со скидкой (price_old > price)
        ↓
[2] Claude (в чате):
    - Читает targets.json
    - Выбирает приёмы под товар (не все 7 — обычно 2-3)
    - Генерирует переработанные description / short_description
    - Сохраняет в proposed_psych.json
        ↓
[3] apply_psych.py --preview-only — diff
        ↓
[4] apply_psych.py — импорт через catalog/import
```

## Использование

```bash
mkdir -p psych_<domain>
cd psych_<domain>
HOROSHOP_DOMAIN=<DOMAIN> HOROSHOP_LOGIN=<LOGIN> HOROSHOP_PASSWORD=<PASSWORD> \
  python3 ${SKILL_DIR}/scripts/find_targets.py [--abc-only] [--discount-only]
```

Опции:
- `--abc-only` — только товары группы A из ABC-анализа (требует `SALES_REPORT.md` рядом)
- `--discount-only` — только товары со скидкой
- `--limit 30` — макс товаров для обработки (default 30, чтоб Claude'у не задохнуться)

## Формат `proposed_psych.json`

```json
[
  {
    "article": "1234",
    "techniques_applied": ["anchoring", "social_proof", "scarcity"],
    "description": "<HTML с инкорпорированными приёмами>",
    "short_description": "Короткий текст с триггером"
  }
]
```

Поля `icons[]` и любые stickers-related — игнорируются. Если нужны кастомные стикеры — создай в админке (**Сайт → Стикеры для товаров → Додати**) отдельно.

## Что НЕ делать

- ❌ Не применять все 7 приёмов сразу к одному товару — выглядит как спам
- ❌ Не врать в scarcity («Залишилось 3 шт» если на самом деле 50) — это ловушка для бренда
- ❌ Не использовать FOMO для дешёвых товаров — не работает, выглядит навязчиво
- ❌ Не переписывать характеристики — только маркетинг-обвязку

## Этика

Психологические триггеры — мощный инструмент. Используй честно:
- Scarcity только если реально мало
- Social proof только с реальными цифрами
- «Купите сегодня и получите скидку» — да; «Цена вырастет завтра» если не вырастет — нет

См. `references/techniques.md` для детальных рецептов и примеров.

## Refs

- `references/techniques.md` — 7 психологических приёмов с UA/RU примерами в тексте
- `references/horoshop_help.md` — выжимка из справки Хорошопа: countdown, скидки, оплата частями, подарки. Стикеры — отдельная админская тема, не в зоне этого скилла.

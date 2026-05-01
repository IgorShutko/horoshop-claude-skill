---
name: horoshop-consistency
description: Поиск противоречий между текстом описания и характеристиками товара на Хорошопе. Используй ВСЕГДА когда пользователь просит "найди несоответствия в карточках", "проверь что описания соответствуют характеристикам", "противоречия в товарах", "consistency check shop". Скилл выгружает каталог через `catalog/export`, парсит описания на упоминания материалов/размеров/стран, сравнивает с `characteristics`. Flag — когда в описании сказано «100% бавовна», в характеристиках указано «поліестер». Помогает поймать баги после copy-paste/переноса с других сайтов.
---

# Horoshop Consistency Check

Поиск конфликтов между описанием и характеристиками товара.

## Что находит (9 типов проверок)

| # | Тип конфликта | Пример |
|---|---|---|
| 1 | Материал текст vs char | description: «100% бавовна», `characteristics.material`: «поліестер» |
| 2 | Страна текст vs char | description: «зроблено в Польщі», `characteristics.country`: «Україна» |
| 3 | Цвет в title vs `color` | title: «чорний», `color`: «білий» |
| 4 | Размер title vs description | title: «50×70», description: «70×100» |
| 5 | Discount math mismatch | discount=20%, но (price_old-price)/price_old = 35% |
| 6 | Placeholder в тексте | «lorem ipsum», «todo», «тест тест» в description |
| 7 | Mod attribute drift | у родителя material=сатин, у модификаций mix микросатин/полиэстер |
| 8 | Negative price | price < 0 (баг импорта) |
| 9 | Negative stock | quantity < 0 на складе |

**Где живут поля** (важно — в API Хорошопа):
- `material`, `country` — внутри `characteristics.<key>` (имя ключа кастомное у каждого магазина)
- `color` — top-level поле товара (`p.color`), НЕ в `characteristics`. Скрипт сначала проверяет top-level, на fallback — `characteristics.color` для нестандартных шаблонов
- `price`, `price_old`, `discount` — top-level
- `residues[]` — top-level массив остатков по складам

## Прозрачность отчёта

Если конфликтов 0 — `CONSISTENCY_REPORT.md` всё равно показывает **что было проверено** (9 типов), чтобы пользователь видел масштаб скана. «0 знайдено» — это валидный результат.

## Почему это важно

Часто баги:
- Copy-paste при создании похожих товаров — забыли поменять характеристики
- Импорт из CSV — колонки сместились
- Перенос с другой платформы — поля не сматчили

Покупатель видит несоответствие → возврат / негативный отзыв / репутация.

## Pipeline

```
[1] Auth + выгрузка каталога
[2] Для каждого главного товара парсим:
    - title
    - description (HTML stripped)
    - short_description
[3] Извлекаем упоминания:
    - материалов (бавовна, поліестер, шкіра, мікросатин и т.д.)
    - стран (Україна, Китай, Польща, Туреччина...)
    - размеров (NN×NN, NN см, NN кг)
    - цветов (чорний, білий, зелений...)
[4] Сравниваем с characteristics
[5] CONSISTENCY_REPORT.md с конфликтами
```

## Использование

```bash
mkdir -p consistency_<domain>
cd consistency_<domain>
HOROSHOP_DOMAIN=<DOMAIN> HOROSHOP_LOGIN=<LOGIN> HOROSHOP_PASSWORD=<PASSWORD> \
  python3 ${SKILL_DIR}/scripts/check_consistency.py
```

Опции:
- `--from-file catalog.json` — без API
- `--lang ua` — язык приоритетный

## Что НЕ делает

- ❌ Не делает семантический анализ — только regex по словарям
- ❌ Не правит автоматом — это нюансная работа
- ❌ Не угадывает синонимы (микросатин ≈ сатин — но скрипт не уверен; flag только на явных конфликтах)

## Limitations

- **Низкий recall, высокая точность.** Скилл лучше скипнет редкий случай чем выдаст false positive
- **Только украинский + русский.** Для других языков понадобятся новые словари

## Refs

- `references/horoshop_help.md` — выжимка из справки Хорошопа: где живут поля (color top-level, characteristics кастомные), Шаблон даних, модификации товаров. **Цитируй её в отчётах со ссылками на источник.**

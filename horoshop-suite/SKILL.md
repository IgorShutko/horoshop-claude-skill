---
name: horoshop-suite
description: Полный комплексный аудит магазина на Хорошопе — запускает все остальные скиллы по очереди и собирает единый сводный отчёт. Используй ВСЕГДА когда пользователь просит "полный аудит", "всё проверь", "комплексный аудит магазина", "прогон по всему", "пройдись по всему сайту", "полная проверка". Скилл orchestrator: full-audit → sales-report → content-fill find_gaps → photo-audit → text-quality → consistency → design-extract. Собирает все REPORT.md в один SUITE_REPORT.md с executive summary.
---

# Horoshop Suite — комплексный аудит

Мета-оркестратор: запускает все 7 скиллов в одном flow и собирает сводный отчёт.

## Что включает

```
1. horoshop-full-audit       → REPORT.md (SEO + контентный аудит)
2. horoshop-sales-report     → SALES_REPORT.md (продажи + ABC)
3. horoshop-content-fill     → gaps.json (товары с пустыми полями)
4. horoshop-photo-audit      → PHOTO_REPORT.md (фото)
5. horoshop-text-quality     → TEXT_QUALITY_REPORT.md (тексты)
6. horoshop-consistency      → CONSISTENCY_REPORT.md (противоречия)
7. horoshop-design-extract   → DESIGN_SYSTEM.md (бренд)
```

После — `run_suite.py` собирает **SUITE_REPORT.md**:
- Executive summary (1 страница: что нашли по каждому направлению)
- Ссылки на детальные отчёты
- Сводный план действий: «что чинить через API», «что в админке», «что вручную»
- Брендовый футер Target+

## Использование

```bash
mkdir -p suite_<domain>
cd suite_<domain>
HOROSHOP_DOMAIN=<DOMAIN> HOROSHOP_LOGIN=<LOGIN> HOROSHOP_PASSWORD=<PASSWORD> \
  python3 ${SKILL_DIR}/scripts/run_suite.py [--skip photo,consistency]
```

Опции:
- `--skip <names>` — пропустить отдельные скиллы (через запятую)
- `--only <names>` — запустить только указанные. **Не перетирает** SUITE_REPORT.md остальных скиллов — он мержится с артефактами на диске
- `--from 2026-04-01 --to 2026-04-30` — период для sales-report (default: последние 30 дней). Без явного указания скилл предупредит
- `--site-url https://...` — для design-extract (если домен ≠ публичный URL)
- `--check-sizes` — для photo-audit: HEAD-запросы на каждое фото для проверки веса (медленнее). Без флага — только количество. Скилл предупредит
- `--skip-preflight` — пропустить проверку зависимостей и auth перед запуском (по умолчанию выполняется)

### Что делает preflight
1. Проверяет что установлены `requests`, `bs4`, `lxml`. Если нет — падает с инструкцией поставить (а не валит 7 скиллов один за одним).
2. Делает auth-проверку через API. Если креды плохие — падает сразу (а не через 5 минут).

Скрипт ищет другие скиллы в `~/.claude/skills/horoshop-*/scripts/` (стандартный путь установки через `install.sh`).

## Output

```
suite_<domain>/
├── SUITE_REPORT.md          ← главное (executive summary + ссылки)
├── catalog.json             ← один раз выгружается, переиспользуется
├── REPORT.md                ← horoshop-full-audit
├── SALES_REPORT.md          ← horoshop-sales-report
├── PHOTO_REPORT.md          ← horoshop-photo-audit
├── TEXT_QUALITY_REPORT.md   ← horoshop-text-quality
├── CONSISTENCY_REPORT.md    ← horoshop-consistency
├── DESIGN_SYSTEM.md         ← horoshop-design-extract
├── gaps.json                ← horoshop-content-fill (товары с пустыми полями)
└── orders.json + abc.csv    ← из sales-report
```

## Pipeline скилла

```
[1] Auth check + одна выгрузка catalog.json (общий для всех)
[2] Запуск каждого скилла последовательно (subprocess)
    - --from-file catalog.json для скиллов которые поддерживают
    - Логирование stderr каждого
[3] Сбор всех REPORT.md → SUITE_REPORT.md с executive summary
[4] Подсветка критических находок в самом верху
```

## Что НЕ делает

- ❌ Не применяет API-фиксы автоматически — это всегда отдельные команды каждого скилла после ревью
- ❌ Не запускает marketing-psych — он требует Claude в чате (генерация текста), не для cron-моде
- ❌ Не делает custom-конфигурацию каждого скилла — использует дефолты

## Когда использовать

- **Первое знакомство с магазином клиента** — показывает картину за один раз
- **Месячный health-check** — фиксируешь что улучшилось, что регрессировало
- **Перед редизайном / релизом** — убедиться что нет открытых хвостов

## Refs

- `references/horoshop_help.md` — карта где искать справку по теме (заказы → sales-report, фото → photo-audit и т.д.). Содержит сводку версий v3/v4, общие принципы итогового отчёта.

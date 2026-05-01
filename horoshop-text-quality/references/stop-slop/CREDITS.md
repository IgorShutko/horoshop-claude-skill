# stop-slop framework

Файлы в этой папке (`phrases.md`, `structures.md`, `examples.md`, `LICENSE`) — копия скилла **stop-slop** от **Hardik Pandya** (https://hvpandya.com).

- Оригинал: https://github.com/hvpandya/stop-slop (или установка через Claude Code skills)
- Лицензия: MIT (см. `LICENSE`)
- Назначение: эталонный список AI-патернов английской прозы

## Как используется в horoshop-text-quality

1. **Структурные правила** (em dashes, binary contrasts, false agency, narrator-from-distance, fragmentation) — **универсальные**, работают для любого языка. Скилл `text_quality.py` детектит их в украинских и русских текстах напрямую.

2. **Фразы** (английские throat-clearers, adverbs, jargon) — переведены на UA/RU в основном `patterns.md` родительской папки. Английские паттерны полезны для магазинов с английской языковой версией.

3. **Scoring (1-10 по 5 измерениям)** — применяется как финальная оценка отчёта (см. `patterns.md`).

Spasiba Hardik'у — фреймворк сэкономил недели работы по типологии AI-стиля.

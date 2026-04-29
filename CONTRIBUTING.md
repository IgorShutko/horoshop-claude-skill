# Contributing

Спасибо что хочешь сделать скилл лучше. Pull requests welcome.

## Что особенно интересно

- **Поддержка кастомных характеристик других магазинов.** Сейчас алгоритм гибкий, но edge cases возможны — например, у магазина другой набор ключей характеристик отличающихся между модификациями
- **Дополнительные фиксы** на основе реальных кейсов
- **Переводы REPORT.md** — сейчас отчёт в основном украинский, можно сделать локализуемым
- **Тесты на API-моках** — сейчас тестим вручную на реальных магазинах
- **Расширенный HTML-парсинг** — например, проверка корректности микроразметки через парсер Schema.org

## Как контрибьютить

1. Форкни репо
2. Создай ветку: `git checkout -b feature/my-fix`
3. Внеси изменения
4. Протестируй на реальном или тестовом магазине Хорошопа
5. Открой PR с описанием что и зачем

## Code style

- Python 3.10+
- Стандартная библиотека + `requests`, `beautifulsoup4`, `lxml`
- Никаких сторонних зависимостей без обсуждения
- Везде `--dry-run` для destructive operations
- Контентные фиксы (description, SEO) — обязательное превью перед записью

## Тестирование

Запусти полный pipeline на тестовом магазине:

```bash
HOROSHOP_DOMAIN=test.com.ua HOROSHOP_LOGIN=api HOROSHOP_PASSWORD=... \
  python3 scripts/audit.py
```

Проверь что `REPORT.md` сгенерировался без ошибок и `findings.json` валиден.

Для фиксов — обязательно `--dry-run` сначала.

---

## 🤝 Hire us / Need consulting?

Если есть конкретная задача по Хорошопу или performance-маркетингу — лучше открыть [issue с шаблоном «🤝 Hire / Consulting»](https://github.com/IgorShutko/horoshop-claude-skill/issues/new?template=consulting.md) или написать напрямую:

- 📺 [TG @shutko_ads](https://t.me/shutko_ads)
- 🌐 [targetplus-agency.com](https://www.targetplus-agency.com/)

Мы из агентства [Target+](https://www.targetplus-agency.com/) — performance-маркетинг для e-commerce из Днепра. Делаем SEO для Horoshop под ключ, настраиваем рекламу в Meta / TikTok / Google.

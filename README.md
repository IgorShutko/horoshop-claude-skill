# Horoshop Full Audit — Claude Code Skill

Скилл для Claude Code, который делает полный технический и SEO-аудит интернет-магазина на платформе [Хорошоп](https://horoshop.ua/) через API + парсинг публичных страниц, формирует отчёт и применяет исправления через API после подтверждения.

## Что умеет

**🟢 Через API (10 фиксов):**
- Обнуляет истёкшие таймеры акций (`countdown_end_time`)
- Заполняет название модификации (`mod_title`) из размера/цвета
- Пересчитывает `discount` если есть `price_old > price`, но `discount=0`
- Заполняет пустые SEO-поля (`seo_title`, `seo_description`, `seo_keywords`, `h1_title`)
- Генерирует `mpn` по шаблону `<PREFIX>-<article>` для фидов Google/Rozetka/FB
- Уникализирует дубли описаний между похожими товарами
- Включает «Оплата частями» Privat + Monobank
- Добавляет стикер «Распродажа» товарам с реальной скидкой
- Чистит inline-стили в HTML описаний
- Настраивает cross-sell (`accessories`, `alt_parent`)

**🟡 Что выводит для ручной правки в админке:**
- Длинные `<title>` категорий (>70 симв) — исправляется через SEO-шаблоны
- Пустой `<meta description>` info-страниц
- Дубли `<h1>` на странице
- Отсутствие `<h1>` на главной
- Скрытые товары (`display_in_showcase=0`) — решить судьбу
- Пустой УКТ ВЕД у товаров
- Пустой SEO-текст у категорий

**🚫 Что НЕ предлагает менять** (это уровень платформы Хорошоп):
- robots.txt, sitemap.xml, микроразметка, hreflang, canonical, URL-формулы

## Установка

### Вариант 1 — одной командой (рекомендую)

```bash
curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash
```

### Вариант 2 — вручную

```bash
git clone https://github.com/IgorShutko/horoshop-claude-skill.git
cd horoshop-claude-skill
mkdir -p ~/.claude/skills/horoshop-full-audit
cp -r SKILL.md scripts references evals ~/.claude/skills/horoshop-full-audit/
chmod +x ~/.claude/skills/horoshop-full-audit/scripts/*.py
pip install --user requests beautifulsoup4 lxml
```

### Вариант 3 — `.skill` файл

Скачай `horoshop-full-audit.skill` из [последнего релиза](https://github.com/IgorShutko/horoshop-claude-skill/releases) и дважды кликни — Claude Code установит автоматически.

## Использование

После установки в любом чате Claude Code напиши, например:

```
Сделай аудит магазина на хорошопе example.com.ua
```

Claude:
1. Спросит креды (или выдаст инструкцию как создать API-юзера, если их ещё нет)
2. Прогонит полный аудит — выгрузит каталог, категории, спарсит публичные страницы
3. Сформирует `REPORT.md` с разделением «через API» / «в админке» / «уже хорошо»
4. Спросит подтверждение по каждому из 10 API-фиксов
5. Применит выбранные пакетным импортом (для контентных — с превью)

## Подготовка магазина

Чтобы скилл смог подключиться, заведи API-пользователя в админке Хорошопа:

1. **Налаштування → Користувачі → Додати**
2. Логин: `api`, пароль на твой выбор, **роль `Owner`** (нужна для чтения каталога и обновления товаров)
3. Передай Claude'у домен + логин/пароль

После аудита можно деактивировать пользователя.

## Структура

```
horoshop-full-audit/
├── SKILL.md                       # Главный файл скилла с pipeline
├── scripts/
│   ├── audit.py                   # Оркестратор: каталог + HTML + report
│   └── apply_fixes.py             # 10 API-фиксов с --dry-run
├── references/
│   ├── api_admin_setup.md         # Инструкция создать API-юзера
│   ├── api_quickref.md            # Справочник Horoshop API
│   ├── audit_checklist.md         # 18 проверок с обоснованиями
│   └── fix_recipes.md             # Рецепты каждого фикса
└── evals/
    └── evals.json                 # Test cases для триггера скилла
```

## Принципы

1. **Только то, что мы можем изменить** — через API или вручную в админке. Если делает только платформа (robots, sitemap, microdata) — не пишем.
2. **Сначала отчёт — потом действия.** Никаких изменений через API без явного подтверждения.
3. **Обоснование каждой рекомендации** — не «сделать X», а «сделать X, потому что Y».
4. **Превью для контентных правок** — описания, SEO-тексты, mod_title.

## Зависимости

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml`, `python-dotenv` (опц.)
- Claude Code

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Вклад

PR welcome. Особенно интересно:
- Поддержка кастомных характеристик других магазинов (сейчас алгоритм гибкий, но edge cases возможны)
- Дополнительные фиксы на основе реальных кейсов
- Перевод REPORT.md на русский / английский / украинский (сейчас в основном украинский)

## Не работает?

Самые частые проблемы:

| Симптом | Причина |
|---|---|
| `User with such username/password not found` | API-юзер не создан — см. инструкцию выше |
| `Code 11` при импорте | Поле не активировано в Шаблоні даних. Включи: **Налаштування → Система → Каталог → Шаблон даних** |
| Пустой HTML страницы | User-Agent блокируется. Скилл использует `Mozilla/5.0 (Horoshop SEO Audit)` — проверь не банится ли в robots/firewall |
| `ModuleNotFoundError: No module named 'requests'` | `pip install --user requests beautifulsoup4 lxml` |

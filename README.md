# Horoshop Claude Skills — набор инструментов для магазинов на Хорошопе

> 🛠 Набор скиллов для Claude Code: SEO-аудит, отчёты по продажам, ABC-анализ, заполнение карточек товаров и другие операции для магазинов на платформе [Хорошоп](https://horoshop.ua/) через API.

🌐 [Русский](README.md) · [Українська](README.uk.md) · [English](README.en.md)

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@shutko__ads-26A5E4?logo=telegram&logoColor=white)](https://t.me/shutko_ads)
[![Agency](https://img.shields.io/badge/Made%20by-Target%2B%20Agency-FF4500)](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme&utm_campaign=horoshop-skill)
[![Built for Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-D97757)](https://claude.com/claude-code)
[![Star History](https://img.shields.io/github/stars/IgorShutko/horoshop-claude-skill?style=social)](https://star-history.com/#IgorShutko/horoshop-claude-skill&Date)

---

## 🎯 От [Target+](https://www.targetplus-agency.com/) — агентства performance-маркетинга

Performance-маркетинг для e-commerce и локального бизнеса из Днепра.
**Meta · TikTok · Google Ads · SEO для Horoshop**.

📺 **TG-канал [@shutko_ads](https://t.me/shutko_ads)** — про рекламу, аналитику и реальные кейсы из агентства.

Эти скиллы — open-source инструменты, которыми мы сами пользуемся при работе с e-commerce клиентами на Хорошопе. Делимся, потому что лучше когда платформа и подрядчики работают чище.

---

## 📦 Скиллы в этом репо

| Скилл | Что делает | Триггер |
|---|---|---|
| **[`horoshop-full-audit`](horoshop-full-audit/)** | Полный SEO + контентный аудит магазина: 22 проверки, 10 автоматических API-фиксов | «сделай аудит магазина на хорошопе», «проверь horoshop магазин» |
| **[`horoshop-sales-report`](horoshop-sales-report/)** | Отчёт по продажам, динамика по дням/неделям/месяцам, ABC-анализ товаров (Парето 80/15/5), разрезы по UTM и способам оплаты/доставки | «отчёт по продажам», «ABC-анализ», «средний чек», «топ товары» |
| **[`horoshop-content-fill`](horoshop-content-fill/)** | Поиск товаров с пустыми `description`, `short_description`, `marketplace_description` + генерация контента под бренд (через Claude) + пакетный импорт через API с превью | «заполни пустые описания», «дополни карточки», «прописать marketplace description» |

Скиллы независимые — устанавливаются вместе, но работают по отдельным триггерам.

Скоро будут добавлены: `horoshop-photo-audit` (количество и качество фото), `horoshop-text-quality` (опечатки, AI-стоп-слоп), и другие.

---

## Что умеет `horoshop-full-audit`

**🟢 Чинит через API (10 пакетных фиксов):**
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

**🟡 Выписывает в отчёт что чинить вручную в админке:**
- Длинные `<title>` категорий (>70 симв) — через SEO-шаблоны
- Пустой `<meta description>` info-страниц
- Дубли `<h1>` на странице
- Отсутствие `<h1>` на главной
- Скрытые товары — решить судьбу
- Пустой УКТ ВЕД у товаров
- Пустой SEO-текст у категорий

**🚫 Не предлагает то, что нельзя изменить ни через API, ни в админке:**
- robots.txt, sitemap.xml, микроразметку, hreflang, canonical, URL-формулы — это уровень платформы Хорошоп

---

## 📊 Как выглядит результат

Полный пример сгенерированного отчёта по тестовому магазину:
**[examples/sample-REPORT.md](examples/sample-REPORT.md)**

Скилл выгружает каталог + категории через API, парсит публичные страницы, формирует REPORT.md с разделением:
- ✅ Что хорошо (не трогаем)
- 🟢 Что чинит сам через API
- 🟡 Что нужно сделать вручную в админке (с указанием **где** именно править)

---

## Установка

### Вариант 1 — одной командой (рекомендую)

```bash
curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash
```

### Вариант 2 — `.skill` файлом

Скачай `horoshop-full-audit.skill` из [последнего релиза](https://github.com/IgorShutko/horoshop-claude-skill/releases) и дважды кликни — Claude Code установит автоматически.

### Вариант 3 — вручную

```bash
git clone https://github.com/IgorShutko/horoshop-claude-skill.git
cd horoshop-claude-skill
mkdir -p ~/.claude/skills/horoshop-full-audit
cp -r SKILL.md scripts references evals ~/.claude/skills/horoshop-full-audit/
chmod +x ~/.claude/skills/horoshop-full-audit/scripts/*.py
pip install --user requests beautifulsoup4 lxml
```

---

## Использование

После установки в любом чате Claude Code напиши:

```
Сделай аудит магазина на хорошопе example.com.ua
```

Claude:
1. Спросит креды (или выдаст инструкцию как создать API-юзера)
2. Прогонит полный аудит — выгрузит каталог, категории, спарсит публичные страницы
3. Сформирует `REPORT.md` с разделением «через API» / «в админке» / «уже хорошо»
4. Спросит подтверждение по каждому из 10 API-фиксов
5. Применит выбранные пакетным импортом (для контентных — с превью)

---

## Подготовка магазина

Чтобы скилл смог подключиться, заведи API-пользователя в админке Хорошопа:

1. **Налаштування → Користувачі → Додати**
2. Логин: `api`, пароль на твой выбор, **роль `Owner`** (нужна для чтения каталога и обновления товаров)
3. Передай Claude'у домен + логин/пароль

После аудита можно деактивировать пользователя.

---

## 🤝 Хочешь чтобы за тебя сделали?

Если не хочешь разбираться сам или нужно больше чем технический аудит — **Target+ делает SEO для магазинов на Хорошопе под ключ:**

- Полный технический + контентный аудит
- Внедрение всех фиксов через API
- Перенастройка SEO-шаблонов в админке
- Уникальные описания товаров и SEO-тексты категорий под ключевые запросы
- Настройка товарных фидов для Rozetka / Google / Meta
- Performance-кампании в Meta / TikTok / Google для готового магазина

📩 [Заявка через сайт](https://www.targetplus-agency.com/) · 💬 [TG @shutko_ads](https://t.me/shutko_ads)

---

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
│   ├── audit_checklist.md         # 22 проверки с обоснованиями
│   └── fix_recipes.md             # Рецепты каждого фикса
├── examples/
│   └── sample-REPORT.md           # Пример выходного отчёта
└── evals/
    └── evals.json                 # Test cases для триггера скилла
```

## Принципы

1. **Только то, что мы можем изменить** — через API или вручную в админке
2. **Сначала отчёт — потом действия.** Никаких изменений через API без явного подтверждения
3. **Обоснование каждой рекомендации** — не «сделать X», а «сделать X, потому что Y»
4. **Превью для контентных правок** — описания, SEO-тексты, mod_title

## Зависимости

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml`
- [Claude Code](https://claude.com/claude-code)

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Вклад

PR welcome. Особенно интересно:
- Поддержка кастомных характеристик других магазинов
- Дополнительные фиксы на основе реальных кейсов
- Перевод REPORT.md на разные языки

См. [CONTRIBUTING.md](CONTRIBUTING.md).

## Не работает?

| Симптом | Причина |
|---|---|
| `User with such username/password not found` | API-юзер не создан — см. инструкцию выше |
| `Code 11` при импорте | Поле не активировано в Шаблоні даних. Включи: **Налаштування → Система → Каталог → Шаблон даних** |
| Пустой HTML страницы | User-Agent блокируется. Скилл использует `Mozilla/5.0 (Horoshop SEO Audit)` — проверь не банится ли в robots/firewall |
| `ModuleNotFoundError: No module named 'requests'` | `pip install --user requests beautifulsoup4 lxml` |

Не помогло? Заводи [issue](https://github.com/IgorShutko/horoshop-claude-skill/issues/new/choose) или пиши в [TG](https://t.me/shutko_ads).

---

## Author

**Игорь Шутко** — основатель [Target+](https://www.targetplus-agency.com/), performance-маркетинг для UA e-commerce.

- 🌐 [targetplus-agency.com](https://www.targetplus-agency.com/)
- 📺 TG [@shutko_ads](https://t.me/shutko_ads)
- 💻 [@IgorShutko](https://github.com/IgorShutko)

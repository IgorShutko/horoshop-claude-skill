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

9 независимых скилла + 1 мета-оркестратор. Устанавливаются вместе, работают по триггерам в чате.

| Скилл | Что делает | Триггер |
|---|---|---|
| **[`horoshop-suite`](horoshop-suite/)** | 🎁 **Мета-оркестратор**: запускает все остальные скиллы по очереди и собирает единый `SUITE_REPORT.md` с executive summary | «полный аудит», «прогон по всему», «всё проверь» |
| **[`horoshop-full-audit`](horoshop-full-audit/)** | Полный SEO + контентный аудит: 22 проверки, 10 автоматических API-фиксов | «сделай аудит магазина», «проверь horoshop магазин» |
| **[`horoshop-sales-report`](horoshop-sales-report/)** | Отчёт по продажам, динамика по дням/неделям/месяцам, ABC-анализ (Парето 80/15/5), разрезы по UTM, способам оплаты/доставки | «отчёт по продажам», «ABC-анализ», «средний чек» |
| **[`horoshop-content-fill`](horoshop-content-fill/)** | Поиск товаров с пустыми `description`/`short_description`/`marketplace_description` + генерация под бренд + импорт через API с превью | «заполни описания», «прописать marketplace description» |
| **[`horoshop-photo-audit`](horoshop-photo-audit/)** | Аудит фото: товары с <N фото, дубли главных изображений, опционально размер файлов через HEAD-запросы | «проверь фото в карточках», «аудит изображений» |
| **[`horoshop-text-quality`](horoshop-text-quality/)** | Качество текстов: AI-слоп, маркетинговая вода, повторы слов, CAPS LOCK, длинные предложения | «найди ChatGPT-тексты», «проверь качество описаний» |
| **[`horoshop-consistency`](horoshop-consistency/)** | Конфликты между текстом и характеристиками: материал/страна/цвет/размер не совпадают | «противоречия в карточках», «характеристики не сходятся» |
| **[`horoshop-design-extract`](horoshop-design-extract/)** | Дизайн-система с публичной главной: цвета, шрифты, CSS-переменные, логотип, favicon | «выгрузи бренд-стиль», «дизайн-система магазина» |
| **[`horoshop-marketing-psych`](horoshop-marketing-psych/)** | Усиление карточек психологическими приёмами (scarcity, anchoring, social proof, loss aversion) с превью и импортом | «маркетинг-приёмы в карточки», «продающий стиль» |

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
**[horoshop-full-audit/examples/sample-REPORT.md](horoshop-full-audit/examples/sample-REPORT.md)**

Скилл выгружает каталог + категории через API, парсит публичные страницы, формирует REPORT.md с разделением:
- ✅ Что хорошо (не трогаем)
- 🟢 Что чинит сам через API
- 🟡 Что нужно сделать вручную в админке (с указанием **где** именно править)

---

## Установка

### Вариант 1 — одной командой (все 9 скиллов сразу)

```bash
curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash
```

Установит все 9 скиллов в `~/.claude/skills/horoshop-*` + Python-зависимости.

### Вариант 2 — вручную, выборочно

```bash
git clone https://github.com/IgorShutko/horoshop-claude-skill.git
cd horoshop-claude-skill

# Установка одного скилла (например, full-audit)
mkdir -p ~/.claude/skills/horoshop-full-audit
cp -r horoshop-full-audit/* ~/.claude/skills/horoshop-full-audit/
chmod +x ~/.claude/skills/horoshop-full-audit/scripts/*.py

# Зависимости
pip install --user requests beautifulsoup4 lxml
```

---

## Использование

После установки в любом чате Claude Code напиши то, что нужно:

| Что хочу | Триггер |
|---|---|
| Прогон по всем направлениям сразу | `Полный аудит магазина на хорошопе example.com.ua` |
| Только SEO + контентный аудит | `Сделай аудит магазина на хорошопе example.com.ua` |
| Продажи + ABC | `Отчёт по продажам за месяц` |
| Заполнить пустые описания | `Заполни пустые описания товаров` |
| Аудит фото | `Проверь фото в карточках` |
| Проверить тексты | `Найди ChatGPT-тексты в карточках` |
| Противоречия | `Проверь характеристики на противоречия` |
| Дизайн-система | `Выгрузи бренд-стиль с главной` |
| Маркетинг-приёмы | `Добавь маркетинг-приёмы в топ-товары` |

Claude:
1. Спросит креды (или выдаст инструкцию как создать API-юзера)
2. Прогонит выбранный скилл (или все — если просили `suite`)
3. Сформирует отчёт с разделением «через API» / «в админке» / «уже хорошо»
4. Спросит подтверждение перед применением фиксов
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
horoshop-claude-skill/
├── horoshop-suite/             # 🎁 мета-оркестратор (запускает остальные)
├── horoshop-full-audit/        # SEO + контентный аудит
├── horoshop-sales-report/      # продажи + ABC + UTM
├── horoshop-content-fill/      # заполнение пустых полей
├── horoshop-photo-audit/       # аудит фото
├── horoshop-text-quality/      # качество текстов / AI-слоп
├── horoshop-consistency/       # противоречия текст ↔ характеристики
├── horoshop-design-extract/    # бренд-стиль с публичной главной
├── horoshop-marketing-psych/   # психо-приёмы для конверсии
├── install.sh                  # Устанавливает все 9 скиллов
├── README.md / README.uk.md / README.en.md
└── LICENSE
```

Каждый скилл — независимая папка с одинаковой структурой:
```
horoshop-<skill>/
├── SKILL.md         # Триггеры + pipeline
├── scripts/         # Python-скрипты
├── references/      # Справочники, рецепты, чеклисты
└── evals/           # Test cases для триггера
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

# Horoshop Claude Skills — набір інструментів для магазинів на Хорошопі

> 🛠 Набір скілів для Claude Code: SEO-аудит, звіти з продажів, ABC-аналіз, заповнення карток товарів та інші операції для магазинів на платформі [Хорошоп](https://horoshop.ua/) через API.

🌐 [Русский](README.md) · [Українська](README.uk.md) · [English](README.en.md)

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@shutko__ads-26A5E4?logo=telegram&logoColor=white)](https://t.me/shutko_ads)
[![Agency](https://img.shields.io/badge/Made%20by-Target%2B%20Agency-FF4500)](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme&utm_campaign=horoshop-skill)
[![Built for Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-D97757)](https://claude.com/claude-code)
[![Star History](https://img.shields.io/github/stars/IgorShutko/horoshop-claude-skill?style=social)](https://star-history.com/#IgorShutko/horoshop-claude-skill&Date)

---

## 🎯 Від [Target+](https://www.targetplus-agency.com/) — агенції performance-маркетингу

Performance-маркетинг для e-commerce та локального бізнесу з Дніпра.
**Meta · TikTok · Google Ads · SEO для Horoshop**.

📺 **TG-канал [@shutko_ads](https://t.me/shutko_ads)** — про рекламу, аналітику та реальні кейси з агенції.

Ці скіли — open-source інструменти, якими ми самі користуємося при роботі з e-commerce клієнтами на Хорошопі. Ділимося, бо краще коли платформа та підрядники працюють чисто.

---

## 📦 Скіли в цьому репо

9 незалежних скілів + 1 мета-оркестратор. Встановлюються разом, працюють за тригерами в чаті.

| Скіл | Що робить | Тригер |
|---|---|---|
| **[`horoshop-suite`](horoshop-suite/)** | 🎁 **Мета-оркестратор**: запускає всі інші скіли по черзі та збирає єдиний `SUITE_REPORT.md` з executive summary | «повний аудит», «прогін по всьому», «все перевір» |
| **[`horoshop-full-audit`](horoshop-full-audit/)** | Повний SEO + контентний аудит: 22 перевірки, 10 автоматичних API-фіксів | «зроби аудит магазину», «перевір horoshop магазин» |
| **[`horoshop-sales-report`](horoshop-sales-report/)** | Звіт з продажів, динаміка по днях/тижнях/місяцях, ABC-аналіз (Парето 80/15/5), розрізи по UTM, способах оплати/доставки | «звіт з продажів», «ABC-аналіз», «середній чек» |
| **[`horoshop-content-fill`](horoshop-content-fill/)** | Пошук товарів з порожніми `description`/`short_description`/`marketplace_description` + генерація під бренд + імпорт через API з прев'ю | «заповни описи», «прописати marketplace description» |
| **[`horoshop-photo-audit`](horoshop-photo-audit/)** | Аудит фото: товари з <N фото, дублі головних зображень, опціонально розмір файлів через HEAD-запити | «перевір фото в картках», «аудит зображень» |
| **[`horoshop-text-quality`](horoshop-text-quality/)** | Якість текстів: AI-слоп, маркетингова вода, повтори слів, CAPS LOCK, довгі речення | «знайди ChatGPT-тексти», «перевір якість описів» |
| **[`horoshop-consistency`](horoshop-consistency/)** | Конфлікти між текстом і характеристиками: матеріал/країна/колір/розмір не збігаються | «суперечності в картках», «характеристики не сходяться» |
| **[`horoshop-design-extract`](horoshop-design-extract/)** | Дизайн-система з публічної головної: кольори, шрифти, CSS-змінні, логотип, favicon | «вивантаж бренд-стиль», «дизайн-система магазину» |
| **[`horoshop-marketing-psych`](horoshop-marketing-psych/)** | Підсилення карток психологічними прийомами (scarcity, anchoring, social proof, loss aversion) з прев'ю та імпортом | «маркетинг-прийоми в картки», «продаючий стиль» |

---

## Що вміє `horoshop-full-audit`

**🟢 Виправляє через API (10 пакетних фіксів):**
- Обнуляє минулі таймери акцій (`countdown_end_time`)
- Заповнює назву модифікації (`mod_title`) з розміру/кольору
- Перераховує `discount` якщо є `price_old > price`, але `discount=0`
- Заповнює порожні SEO-поля (`seo_title`, `seo_description`, `seo_keywords`, `h1_title`)
- Генерує `mpn` за шаблоном `<PREFIX>-<article>` для фідів Google/Rozetka/FB
- Унікалізує дублі описів між схожими товарами
- Вмикає «Оплата частинами» Privat + Monobank
- Додає стікер «Распродаж» товарам з реальною знижкою
- Чистить inline-стилі в HTML описів
- Налаштовує cross-sell (`accessories`, `alt_parent`)

**🟡 Виписує у звіт що виправляти вручну в адмінці:**
- Довгі `<title>` категорій (>70 симв) — через SEO-шаблони
- Порожній `<meta description>` інфо-сторінок
- Дублі `<h1>` на сторінці
- Відсутність `<h1>` на головній
- Приховані товари — вирішити долю
- Порожній УКТ ВЕД у товарів
- Порожній SEO-текст у категорій

**🚫 Не пропонує того, що не можна змінити ані через API, ані в адмінці:**
- robots.txt, sitemap.xml, мікророзмітку, hreflang, canonical, URL-формули — це рівень платформи Хорошоп

---

## 📊 Як виглядає результат

Повний приклад згенерованого звіту:
**[examples/sample-REPORT.md](examples/sample-REPORT.md)**

Скіл вивантажує каталог + категорії через API, парсить публічні сторінки, формує REPORT.md з поділом:
- ✅ Що добре (не чіпаємо)
- 🟢 Що виправляє сам через API
- 🟡 Що треба зробити вручну в адмінці (з вказівкою **де саме** правити)

---

## Встановлення

### Варіант 1 — однією командою (всі 9 скілів одразу)

```bash
curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash
```

Встановить усі 9 скілів у `~/.claude/skills/horoshop-*` + Python-залежності.

### Варіант 2 — вручну, вибірково

```bash
git clone https://github.com/IgorShutko/horoshop-claude-skill.git
cd horoshop-claude-skill

# Встановлення одного скіла (наприклад, full-audit)
mkdir -p ~/.claude/skills/horoshop-full-audit
cp -r horoshop-full-audit/* ~/.claude/skills/horoshop-full-audit/
chmod +x ~/.claude/skills/horoshop-full-audit/scripts/*.py

# Залежності
pip install --user requests beautifulsoup4 lxml
```

---

## Використання

Після встановлення у будь-якому чаті Claude Code напиши те, що треба:

| Що хочу | Тригер |
|---|---|
| Прогін по всіх напрямках одразу | `Повний аудит магазину на хорошопі example.com.ua` |
| Тільки SEO + контентний аудит | `Зроби аудит магазину на хорошопі example.com.ua` |
| Продажі + ABC | `Звіт з продажів за місяць` |
| Заповнити порожні описи | `Заповни порожні описи товарів` |
| Аудит фото | `Перевір фото в картках` |
| Перевірити тексти | `Знайди ChatGPT-тексти в картках` |
| Суперечності | `Перевір характеристики на суперечності` |
| Дизайн-система | `Вивантаж бренд-стиль з головної` |
| Маркетинг-прийоми | `Додай маркетинг-прийоми в топ-товари` |

Claude:
1. Спитає креди (або видасть інструкцію як створити API-юзера)
2. Прожене вибраний скіл (або всі — якщо просили `suite`)
3. Сформує звіт з поділом «через API» / «в адмінці» / «вже добре»
4. Спитає підтвердження перед застосуванням фіксів
5. Застосує вибрані пакетним імпортом (для контентних — з прев'ю)

---

## Підготовка магазину

Щоб скіл зміг підключитися, заведи API-користувача в адмінці Хорошопа:

1. **Налаштування → Користувачі → Додати**
2. Логін: `api`, пароль на твій вибір, **роль `Owner`** (потрібна для читання каталогу та оновлення товарів)
3. Передай Claude'у домен + логін/пароль

Після аудиту можна деактивувати користувача.

---

## 🤝 Хочеш щоб за тебе зробили?

Якщо не хочеш розбиратися сам або потрібно більше ніж технічний аудит — **Target+ робить SEO для магазинів на Хорошопі під ключ:**

- Повний технічний + контентний аудит
- Впровадження всіх фіксів через API
- Переналаштування SEO-шаблонів в адмінці
- Унікальні описи товарів і SEO-тексти категорій під ключові запити
- Налаштування товарних фідів для Rozetka / Google / Meta
- Performance-кампанії в Meta / TikTok / Google для готового магазину

📩 [Заявка через сайт](https://www.targetplus-agency.com/) · 💬 [TG @shutko_ads](https://t.me/shutko_ads)

---

## Структура

```
horoshop-claude-skill/
├── horoshop-suite/             # 🎁 мета-оркестратор (запускає інші)
├── horoshop-full-audit/        # SEO + контентний аудит
├── horoshop-sales-report/      # продажі + ABC + UTM
├── horoshop-content-fill/      # заповнення порожніх полів
├── horoshop-photo-audit/       # аудит фото
├── horoshop-text-quality/      # якість текстів / AI-слоп
├── horoshop-consistency/       # суперечності текст ↔ характеристики
├── horoshop-design-extract/    # бренд-стиль з публічної головної
├── horoshop-marketing-psych/   # психо-прийоми для конверсії
├── install.sh                  # Встановлює всі 9 скілів
├── README.md / README.uk.md / README.en.md
└── LICENSE
```

Кожен скіл — незалежна папка з однаковою структурою:
```
horoshop-<skill>/
├── SKILL.md         # Тригери + pipeline
├── scripts/         # Python-скрипти
├── references/      # Довідники, рецепти, чеклісти
└── evals/           # Test cases для тригеру
```

## Принципи

1. **Тільки те, що ми можемо змінити** — через API або вручну в адмінці
2. **Спершу звіт — потім дії.** Жодних змін через API без явного підтвердження
3. **Обґрунтування кожної рекомендації** — не «зробити X», а «зробити X, тому що Y»
4. **Прев'ю для контентних правок** — описи, SEO-тексти, mod_title

## Залежності

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml`
- [Claude Code](https://claude.com/claude-code)

## Ліцензія

MIT — див. [LICENSE](LICENSE).

## Внесок

PR welcome. Особливо цікаво:
- Підтримка кастомних характеристик інших магазинів
- Додаткові фікси на основі реальних кейсів
- Переклад REPORT.md на різні мови

Див. [CONTRIBUTING.md](CONTRIBUTING.md).

## Не працює?

| Симптом | Причина |
|---|---|
| `User with such username/password not found` | API-юзер не створений — див. інструкцію вище |
| `Code 11` при імпорті | Поле не активоване в Шаблоні даних. Увімкни: **Налаштування → Система → Каталог → Шаблон даних** |
| Порожній HTML сторінки | User-Agent блокується. Скіл використовує `Mozilla/5.0 (Horoshop SEO Audit)` — перевір чи не банить його robots/firewall |
| `ModuleNotFoundError: No module named 'requests'` | `pip install --user requests beautifulsoup4 lxml` |

Не допомогло? Заводь [issue](https://github.com/IgorShutko/horoshop-claude-skill/issues/new/choose) або пиши в [TG](https://t.me/shutko_ads).

---

## Author

**Ігор Шутко** — засновник [Target+](https://www.targetplus-agency.com/), performance-маркетинг для UA e-commerce.

- 🌐 [targetplus-agency.com](https://www.targetplus-agency.com/)
- 📺 TG [@shutko_ads](https://t.me/shutko_ads)
- 💻 [@IgorShutko](https://github.com/IgorShutko)

# Horoshop Claude Skills — toolkit for Horoshop stores

> 🛠 A set of Claude Code skills: SEO audit, sales reports, ABC analysis, product card filling, and other operations for stores on the [Horoshop](https://horoshop.ua/) e-commerce platform via API.

🌐 [Русский](README.md) · [Українська](README.uk.md) · [English](README.en.md)

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-@shutko__ads-26A5E4?logo=telegram&logoColor=white)](https://t.me/shutko_ads)
[![Agency](https://img.shields.io/badge/Made%20by-Target%2B%20Agency-FF4500)](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme_en&utm_campaign=horoshop-skill)
[![Built for Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-D97757)](https://claude.com/claude-code)
[![Star History](https://img.shields.io/github/stars/IgorShutko/horoshop-claude-skill?style=social)](https://star-history.com/#IgorShutko/horoshop-claude-skill&Date)

---

## 🎯 Built by [Target+](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme_en&utm_campaign=horoshop-skill) — performance marketing agency

Performance marketing for e-commerce and local business from Dnipro, Ukraine.
**Meta · TikTok · Google Ads · SEO for Horoshop**.

📺 **TG channel [@shutko_ads](https://t.me/shutko_ads)** — about ads, analytics, real-world cases.

These skills are open-source tools we use ourselves on e-commerce clients running on Horoshop. We're sharing because the platform and contractors should both work clean.

---

## 📦 Skills in this repo

9 independent skills + 1 meta-orchestrator. Installed together, triggered by phrases in chat.

| Skill | What it does | Trigger |
|---|---|---|
| **[`horoshop-suite`](horoshop-suite/)** | 🎁 **Meta-orchestrator**: runs all other skills sequentially and assembles a single `SUITE_REPORT.md` with executive summary | "full audit", "comprehensive check", "run everything" |
| **[`horoshop-full-audit`](horoshop-full-audit/)** | Full SEO + content audit: 22 checks, 10 automated API fixes | "audit my store", "check horoshop store" |
| **[`horoshop-sales-report`](horoshop-sales-report/)** | Sales report: daily/weekly/monthly trends, ABC analysis (Pareto 80/15/5), UTM and payment/delivery breakdowns | "sales report", "ABC analysis", "average order value" |
| **[`horoshop-content-fill`](horoshop-content-fill/)** | Find products with empty `description`/`short_description`/`marketplace_description` + brand-aware generation + API import with preview | "fill empty descriptions", "write marketplace description" |
| **[`horoshop-photo-audit`](horoshop-photo-audit/)** | Photo audit: products with <N photos, duplicate main images, optional file size via HEAD requests | "check product photos", "image audit" |
| **[`horoshop-text-quality`](horoshop-text-quality/)** | Text quality: AI-slop, marketing fluff, repeated words, CAPS LOCK, long sentences | "find ChatGPT-generated text", "check description quality" |
| **[`horoshop-consistency`](horoshop-consistency/)** | Conflicts between text and characteristics: material/country/color/size mismatches | "contradictions in cards", "characteristics don't match" |
| **[`horoshop-design-extract`](horoshop-design-extract/)** | Design system from public homepage: colors, fonts, CSS variables, logo, favicon | "extract brand style", "store design system" |
| **[`horoshop-marketing-psych`](horoshop-marketing-psych/)** | Strengthen product cards with psychological techniques (scarcity, anchoring, social proof, loss aversion) with preview and import | "marketing tricks for cards", "selling style" |

---

## What `horoshop-full-audit` does

**🟢 Auto-fixable via API (10 batch fixes):**
- Resets expired sale countdown timers (`countdown_end_time`)
- Fills modification names (`mod_title`) from size/color attributes
- Recalculates `discount` when `price_old > price` but `discount=0`
- Fills empty SEO fields (`seo_title`, `seo_description`, `seo_keywords`, `h1_title`)
- Generates `mpn` using `<PREFIX>-<article>` template for Google/Rozetka/FB feeds
- De-duplicates description text across similar products
- Enables installment payments (Privat + Monobank)
- Adds "Sale" sticker to products with active discount
- Strips inline styles from HTML descriptions
- Configures cross-sell (`accessories`, `alt_parent`)

**🟡 Reports for manual fix in admin panel:**
- Long category `<title>` tags (>70 chars) — fix via SEO templates
- Empty `<meta description>` on info pages
- Multiple `<h1>` tags on a page
- Missing `<h1>` on the homepage
- Hidden products (`display_in_showcase=0`) — decide their fate
- Empty UKT VED codes
- Empty SEO text on category pages

**🚫 Doesn't suggest changes that can't be made via API or admin panel:**
- robots.txt, sitemap.xml, microdata, hreflang, canonical, URL formulas — these are platform-level on Horoshop

---

## 📊 What the output looks like

Full sample of the auto-generated report:
**[examples/sample-REPORT.md](examples/sample-REPORT.md)**

The skill exports the catalog + categories via API, parses public pages, then generates `REPORT.md` with three sections:
- ✅ What's good (don't touch)
- 🟢 What it auto-fixes via API
- 🟡 What needs manual work in admin panel (with **exact location** to edit)

---

## Installation

### Option 1 — one-liner (all 9 skills at once)

```bash
curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash
```

Installs all 9 skills into `~/.claude/skills/horoshop-*` + Python deps.

### Option 2 — manual, selective

```bash
git clone https://github.com/IgorShutko/horoshop-claude-skill.git
cd horoshop-claude-skill

# Install one skill (e.g. full-audit)
mkdir -p ~/.claude/skills/horoshop-full-audit
cp -r horoshop-full-audit/* ~/.claude/skills/horoshop-full-audit/
chmod +x ~/.claude/skills/horoshop-full-audit/scripts/*.py

# Dependencies
pip install --user requests beautifulsoup4 lxml
```

---

## Usage

After installation, in any Claude Code chat write what you need:

| What I want | Trigger |
|---|---|
| Run all skills at once | `Full audit of my Horoshop store at example.com.ua` |
| SEO + content audit only | `Run audit of my Horoshop store at example.com.ua` |
| Sales + ABC | `Sales report for the past month` |
| Fill empty descriptions | `Fill empty product descriptions` |
| Photo audit | `Check product photos` |
| Text quality | `Find ChatGPT-generated text in cards` |
| Consistency | `Check characteristics for contradictions` |
| Design system | `Extract brand style from homepage` |
| Marketing tricks | `Add marketing techniques to top products` |

Claude will:
1. Ask for credentials (or show instructions for creating an API user)
2. Run the requested skill (or all of them — if `suite` was triggered)
3. Generate the report with the three-section breakdown
4. Ask for confirmation before applying fixes
5. Apply the selected fixes via batch import (with preview for content-touching ones)

---

## Store preparation

To let the skill connect, create an API user in your Horoshop admin:

1. **Settings → Users → Add user**
2. Login: `api`, password of your choice, **role `Owner`** (needed to read catalog and update products)
3. Pass the domain + login/password to Claude

You can deactivate the user after the audit.

---

## 🤝 Want it done for you?

If you'd rather not DIY, or need more than just a technical audit — **Target+ does end-to-end SEO for Horoshop stores:**

- Full technical + content audit
- Implementing all fixes via API
- Reconfiguring SEO templates in admin
- Unique product descriptions and category SEO copy targeting key queries
- Setting up product feeds for Rozetka / Google / Meta
- Performance campaigns on Meta / TikTok / Google for ready stores

📩 [Contact via website](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme_en&utm_campaign=hire-cta) · 💬 [TG @shutko_ads](https://t.me/shutko_ads)

---

## Repository structure

```
horoshop-claude-skill/
├── horoshop-suite/             # 🎁 meta-orchestrator (runs other skills)
├── horoshop-full-audit/        # SEO + content audit
├── horoshop-sales-report/      # sales + ABC + UTM
├── horoshop-content-fill/      # fill empty fields
├── horoshop-photo-audit/       # photo audit
├── horoshop-text-quality/      # text quality / AI-slop
├── horoshop-consistency/       # text ↔ characteristics conflicts
├── horoshop-design-extract/    # brand style from public homepage
├── horoshop-marketing-psych/   # psych techniques for conversion
├── install.sh                  # Installs all 9 skills
├── README.md / README.uk.md / README.en.md
└── LICENSE
```

Each skill is a self-contained folder with the same structure:
```
horoshop-<skill>/
├── SKILL.md         # Triggers + pipeline
├── scripts/         # Python scripts
├── references/      # Reference docs, recipes, checklists
└── evals/           # Test cases for triggering
```

## Principles

1. **Only fixes we can actually apply** — via API or manually in admin. If the platform owns it (robots, sitemap, microdata), we don't write about it
2. **Report first, action second.** Never modifies anything via API without explicit confirmation
3. **Rationale for every recommendation** — not "do X" but "do X because Y, otherwise Z"
4. **Preview for content edits** — descriptions, SEO copy, mod_title

## Dependencies

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml`
- [Claude Code](https://claude.com/claude-code)

## License

MIT — see [LICENSE](LICENSE).

## Contributing

PRs welcome. Especially interested in:
- Custom characteristics support for other stores (current algorithm is flexible but edge cases exist)
- Additional fixes based on real-world cases
- REPORT.md translations into other languages

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

| Symptom | Cause |
|---|---|
| `User with such username/password not found` | API user not created — see setup above |
| `Code 11` on import | Field not enabled in Data Template. Enable: **Settings → System → Catalog → Data Template** |
| Empty HTML response | User-Agent is being blocked. The skill uses `Mozilla/5.0 (Horoshop SEO Audit)` — check robots/firewall |
| `ModuleNotFoundError: No module named 'requests'` | `pip install --user requests beautifulsoup4 lxml` |

Still stuck? Open an [issue](https://github.com/IgorShutko/horoshop-claude-skill/issues/new/choose) or ping us on [Telegram](https://t.me/shutko_ads).

---

## Author

**Igor Shutko** — founder of [Target+](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme_en&utm_campaign=author), performance marketing for UA e-commerce.

- 🌐 [targetplus-agency.com](https://www.targetplus-agency.com/?utm_source=github&utm_medium=readme_en&utm_campaign=author)
- 📺 TG [@shutko_ads](https://t.me/shutko_ads)
- 💻 [@IgorShutko](https://github.com/IgorShutko)

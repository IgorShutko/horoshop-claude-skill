# Horoshop Full Audit — Claude Code Skill

> 🛠 A Claude Code skill that runs a full SEO audit on stores built on the [Horoshop](https://horoshop.ua/) e-commerce platform via API + public-page parsing, generates a structured report, and applies fixes through the API after confirmation.

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

This skill is an open-source tool we use ourselves on e-commerce clients running on Horoshop. We're sharing because the platform and contractors should both work clean.

---

## What it does

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

### Option 1 — one-liner (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash
```

### Option 2 — `.skill` file

Download `horoshop-full-audit.skill` from the [latest release](https://github.com/IgorShutko/horoshop-claude-skill/releases) and double-click — Claude Code installs it automatically.

### Option 3 — manual

```bash
git clone https://github.com/IgorShutko/horoshop-claude-skill.git
cd horoshop-claude-skill
mkdir -p ~/.claude/skills/horoshop-full-audit
cp -r SKILL.md scripts references evals ~/.claude/skills/horoshop-full-audit/
chmod +x ~/.claude/skills/horoshop-full-audit/scripts/*.py
pip install --user requests beautifulsoup4 lxml
```

---

## Usage

After installation, in any Claude Code chat write:

```
Run a full audit of my Horoshop store at example.com.ua
```

Claude will:
1. Ask for credentials (or show instructions for creating an API user)
2. Run the full audit — export catalog, categories, parse public pages
3. Generate `REPORT.md` with the three-section breakdown
4. Ask for confirmation on each of the 10 API fixes
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
horoshop-full-audit/
├── SKILL.md                       # Main skill file with pipeline
├── scripts/
│   ├── audit.py                   # Orchestrator: catalog + HTML + report
│   └── apply_fixes.py             # 10 API fixes with --dry-run
├── references/
│   ├── api_admin_setup.md         # API user setup guide
│   ├── api_quickref.md            # Horoshop API reference
│   ├── audit_checklist.md         # 22 checks with rationale
│   └── fix_recipes.md             # Recipes for each fix
├── examples/
│   └── sample-REPORT.md           # Sample output
└── evals/
    └── evals.json                 # Test cases for skill triggering
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

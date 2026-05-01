#!/usr/bin/env python3
"""Извлечение дизайн-системы Horoshop магазина (цвета, шрифты, лого).

Использование:
  python3 extract.py --url https://example.com.ua [--max-css 5] [--no-download]
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

session = requests.Session()
# Современный браузерный UA — некоторые магазины отдают пустую заглушку bot-friendly UA
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
})


def fetch(url, **kw):
    try:
        r = session.get(url, timeout=30, allow_redirects=True, **kw)
        return r.status_code, r.text, r.content, r.url
    except Exception as e:
        return 0, str(e), b"", url


def write_fail_report(url, reason_code, message, html_preview=""):
    """Пишет понятный DESIGN_SYSTEM.md при провале — чтобы пользователь сразу видел что случилось."""
    md = []
    md.append(f"# Дизайн-система — НЕ ВДАЛОСЯ ВИТЯГТИ\n")
    md.append(f"**URL:** {url}")
    md.append(f"**Помилка:** `{reason_code}`")
    md.append(f"**Опис:** {message}\n")

    md.append("## Що це означає\n")
    explanations = {
        "http_error": "Сервер повернув не-200 статус. Перевір домен (опечатка?), доступність сайту.",
        "html_too_short": "Сторінка повернула менше 1 КБ HTML. Це або заглушка анти-бота, або сайт лежить.",
        "cloudflare_waf": "Cloudflare блокує запити з простого Python-клієнта. Потрібен браузерний рендеринг.",
        "no_css_no_logo": "HTML отриманий, але без CSS-посилань і логотипа. Контент рендериться через JS (SPA-стиль) або лендінг-конструктор не використовує зовнішні стилі.",
        "playwright_failed": "Headless Chromium не зміг рендернути сторінку. Перевір що Playwright встановлений: `pip install playwright && playwright install chromium`.",
    }
    md.append(explanations.get(reason_code, "Невідома причина."))
    md.append("")

    md.append("## Як виправити\n")
    if reason_code in ("html_too_short", "no_css_no_logo", "cloudflare_waf"):
        md.append("Запусти з headless-браузером:\n")
        md.append("```bash")
        md.append("pip install playwright")
        md.append("playwright install chromium")
        md.append(f"PLAYWRIGHT=1 python3 extract.py --url {url}")
        md.append("```\n")
        md.append("Або зібрати дизайн-систему вручну:")
        md.append("- Зайти на сайт у звичайному браузері")
        md.append("- Через DevTools → Network → відфільтрувати CSS — побачиш реальні стилі")
        md.append("- Логотип — Inspect Element на лого в шапці")
    elif reason_code == "playwright_failed":
        md.append("Перевстанови Playwright:")
        md.append("```bash")
        md.append("pip install --upgrade playwright")
        md.append("playwright install chromium")
        md.append("```")
    else:
        md.append("Перевір домен та доступність сайту. Якщо все ОК — відкрий issue в репо скілла.")
    md.append("")

    if html_preview:
        md.append("## Перші 500 символів отриманого HTML (для діагностики)\n")
        md.append("```html")
        md.append(html_preview[:500])
        md.append("```\n")

    md.append("---\n")
    md.append("🎨 *Згенеровано скілом [horoshop-design-extract](https://github.com/IgorShutko/horoshop-claude-skill) — Target+ Agency.*")

    Path("DESIGN_SYSTEM.md").write_text("\n".join(md), encoding="utf-8")
    Path("design.json").write_text(json.dumps({
        "domain": urlparse(url).netloc,
        "url": url,
        "extracted": False,
        "fail_reason": reason_code,
        "fail_message": message,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → DESIGN_SYSTEM.md з описом помилки записаний")


def fetch_via_playwright(url):
    """Опциональный fallback на Playwright для JS-rendered сайтов.

    Активируется через `PLAYWRIGHT=1` env-переменную.
    Требует: pip install playwright + playwright install chromium

    Возвращает (status_code, rendered_html, content_bytes, final_url).
    Если Playwright не установлен — возвращает (0, ...) с фейлом.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return 0, ("Playwright не встановлений. Поставь: "
                   "pip install playwright && playwright install chromium"), b"", url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                locale="uk-UA",
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60_000)
            html = page.content()
            final_url = page.url
            browser.close()
        return 200, html, html.encode("utf-8"), final_url
    except Exception as e:
        return 0, f"Playwright помилка: {e}", b"", url


# ─── Извлечение из CSS ─────────────────────────────────────────────────────

CSS_VAR_RE = re.compile(r"--([\w-]+)\s*:\s*([^;{}]+);")
COLOR_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
COLOR_RGB_RE = re.compile(r"rgba?\([^)]+\)")
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;{}]+)", re.IGNORECASE)


def normalize_hex(c):
    """Нормализует #abc → #aabbcc."""
    c = c.strip().lower()
    if not c.startswith("#"):
        return c
    body = c[1:]
    if len(body) == 3:
        return "#" + "".join(ch * 2 for ch in body)
    if len(body) == 4:
        return "#" + "".join(ch * 2 for ch in body[:3])  # игнорируем alpha
    if len(body) == 8:
        return "#" + body[:6]
    return c


def extract_from_css(css_text):
    """Возвращает {variables, colors_count, fonts}."""
    variables = {}
    for name, val in CSS_VAR_RE.findall(css_text):
        variables[name.strip()] = val.strip()

    colors = []
    for m in COLOR_HEX_RE.findall(css_text):
        colors.append(normalize_hex(m))
    for m in COLOR_RGB_RE.findall(css_text):
        colors.append(m.strip())

    color_counts = Counter(colors)

    fonts = []
    for fams in FONT_FAMILY_RE.findall(css_text):
        # Разделим по запятой, обработаем кавычки
        names = [f.strip().strip('"').strip("'") for f in fams.split(",")]
        names = [n for n in names if n and not n.startswith("var(") and not n.startswith("inherit")]
        fonts.extend(names)

    font_counts = Counter(fonts)

    return {
        "variables": variables,
        "colors": [{"value": c, "count": n} for c, n in color_counts.most_common(30)],
        "fonts": [{"family": f, "count": n} for f, n in font_counts.most_common(15)],
    }


# ─── Скачивание ассетов ───────────────────────────────────────────────────

def download_asset(url, dest_path):
    """Скачивает файл, возвращает True если успех."""
    sc, _, content, _ = fetch(url)
    if sc != 200 or not content:
        return False
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(dest_path).write_bytes(content)
    return True


# ─── Парсинг HTML ─────────────────────────────────────────────────────────

def parse_homepage(url, html):
    soup = BeautifulSoup(html, "lxml")
    head = soup.find("head") or soup
    body = soup.find("body") or soup

    info = {
        "url": url,
        "title": (head.find("title").get_text().strip() if head.find("title") else ""),
        "lang": (soup.find("html").get("lang") if soup.find("html") else ""),
        "viewport": (head.find("meta", attrs={"name": "viewport"}) or {}).get("content", "") if head.find("meta", attrs={"name": "viewport"}) else "",
        "css_files": [],
        "logo_url": "",
        "favicon_url": "",
        "og_image": "",
        "inline_styles": "",
    }

    # CSS файлы
    for link in head.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            full = urljoin(url, href)
            info["css_files"].append(full)

    # Inline <style>
    inline = []
    for style in head.find_all("style"):
        if style.string:
            inline.append(style.string)
    info["inline_styles"] = "\n".join(inline)

    # Favicon
    for rel in ("icon", "shortcut icon"):
        link = head.find("link", rel=rel)
        if link and link.get("href"):
            info["favicon_url"] = urljoin(url, link.get("href"))
            break

    # OG image (часто = логотип в OG для главной)
    og = head.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        info["og_image"] = og.get("content")

    # Логотип — ищем img с классом / alt содержащим "logo"
    for img in body.find_all("img"):
        src = img.get("src", "")
        cls = " ".join(img.get("class", [])).lower()
        alt = (img.get("alt") or "").lower()
        if "logo" in cls or "logo" in alt or "лого" in alt:
            info["logo_url"] = urljoin(url, src)
            break

    # Если логотипа явного нет — используем og:image как fallback
    if not info["logo_url"] and info["og_image"]:
        info["logo_url"] = info["og_image"]

    return info


def main():
    parser = argparse.ArgumentParser(description="Extract design system from Horoshop store")
    parser.add_argument("--url", required=True, help="Главная страница магазина")
    parser.add_argument("--max-css", type=int, default=5, help="Максимум CSS-файлов скачать (default 5)")
    parser.add_argument("--no-download", action="store_true", help="Не скачивать ассеты")
    args = parser.parse_args()

    url = args.url.rstrip("/") + "/"
    print(f"=== Design extract {url} ===\n")

    use_playwright = os.environ.get("PLAYWRIGHT") == "1"
    if use_playwright:
        print("  PLAYWRIGHT=1 → використовую headless Chromium")
        print("[1/4] Завантажую главну (Playwright)...")
        sc, html, _, final = fetch_via_playwright(url)
        if sc != 200:
            print(f"  ❌ Playwright fail: {html[:200]}", file=sys.stderr)
            write_fail_report(url, "playwright_failed", html[:500])
            sys.exit(2)
    else:
        print("[1/4] Завантажую главну (requests)...")
        sc, html, _, final = fetch(url)
        if sc != 200:
            print(f"ERROR: статус {sc} — головна не доступна", file=sys.stderr)
            write_fail_report(url, "http_error", f"HTTP {sc}: {html[:200]}")
            sys.exit(1)

    # Sanity-check: HTML должен быть осмысленного размера
    html_len = len(html)
    print(f"  HTML розмір: {html_len} байт")
    if html_len < 1000:
        msg = f"HTML занадто короткий ({html_len} байт). Можливо: JS-SPA / WAF / сайт лежить."
        print(f"\n❌ ERROR: {msg}", file=sys.stderr)
        if not use_playwright:
            print("   Спробуй з Playwright: PLAYWRIGHT=1 python3 extract.py --url ...", file=sys.stderr)
        write_fail_report(url, "html_too_short", msg, html_preview=html)
        sys.exit(2)

    # Детект Cloudflare challenge
    lower_html = html[:5000].lower()
    if "cloudflare" in lower_html and ("challenge" in lower_html or "checking your browser" in lower_html):
        msg = "Cloudflare challenge виявлено. Сайт за WAF."
        print(f"\n❌ ERROR: {msg}", file=sys.stderr)
        if not use_playwright:
            print("   Workaround: PLAYWRIGHT=1 python3 extract.py --url ...", file=sys.stderr)
        write_fail_report(url, "cloudflare_waf", msg, html_preview=html[:500])
        sys.exit(2)

    # 2. HTML парсинг
    info = parse_homepage(url, html)
    print(f"  CSS files: {len(info['css_files'])}, logo: {bool(info['logo_url'])}, favicon: {bool(info['favicon_url'])}")

    # Sanity: должен быть хотя бы какой-то <head> / <body>
    if not info["css_files"] and not info["inline_styles"] and not info["logo_url"] and not info["favicon_url"]:
        msg = ("HTML отриманий, але в ньому немає ані CSS, ані лого, ані favicon. "
               "Скоріше за все JS-SPA або лендінг-конструктор без зовнішніх стилів.")
        print(f"\n❌ ERROR: {msg}", file=sys.stderr)
        if not use_playwright:
            print("   Спробуй: PLAYWRIGHT=1 python3 extract.py --url ...", file=sys.stderr)
        write_fail_report(url, "no_css_no_logo", msg, html_preview=html[:1000])
        sys.exit(3)

    # 3. CSS — соединяем inline + первые N внешних
    print(f"[2/4] Парсинг CSS (inline + до {args.max_css} файлов)...")
    all_css = info["inline_styles"]
    for i, css_url in enumerate(info["css_files"][:args.max_css]):
        sc, txt, _, _ = fetch(css_url)
        if sc == 200:
            all_css += "\n/* === " + css_url + " === */\n" + txt
            if not args.no_download:
                Path("assets").mkdir(exist_ok=True)
                fname = f"assets/css_{i+1}.css"
                Path(fname).write_text(txt, encoding="utf-8")

    css_extract = extract_from_css(all_css)
    print(f"  Цветов уникальных: {len(css_extract['colors'])}, шрифтов: {len(css_extract['fonts'])}, переменных: {len(css_extract['variables'])}")

    if len(css_extract["colors"]) == 0 and len(css_extract["fonts"]) == 0:
        print(f"\n⚠️ WARNING: CSS отриманий, але в ньому 0 кольорів і 0 шрифтів.", file=sys.stderr)
        print(f"   Це нетипово для працюючого сайту. Перевір вручну: {url}", file=sys.stderr)
        # Не выходим с ошибкой — может быть редкий случай. Просто предупреждаем.

    # 4. Скачивание ассетов
    if not args.no_download:
        print("[3/4] Скачиваю ассеты...")
        if info["logo_url"]:
            ext = Path(urlparse(info["logo_url"]).path).suffix or ".png"
            ok = download_asset(info["logo_url"], f"assets/logo{ext}")
            print(f"  logo: {'✓' if ok else '✗'} {info['logo_url']}")
        if info["favicon_url"]:
            ext = Path(urlparse(info["favicon_url"]).path).suffix or ".ico"
            ok = download_asset(info["favicon_url"], f"assets/favicon{ext}")
            print(f"  favicon: {'✓' if ok else '✗'} {info['favicon_url']}")
    else:
        print("[3/4] Skipping download (--no-download)")

    # 5. Output
    print("[4/4] Сохраняю design.json + DESIGN_SYSTEM.md...")
    design = {
        "domain": urlparse(url).netloc,
        "url": url,
        "page": {
            "title": info["title"],
            "lang": info["lang"],
            "viewport": info["viewport"],
        },
        "logo_url": info["logo_url"],
        "favicon_url": info["favicon_url"],
        "og_image": info["og_image"],
        "css_files_count": len(info["css_files"]),
        "css_variables": css_extract["variables"],
        "colors_top30": css_extract["colors"],
        "fonts": css_extract["fonts"],
    }
    Path("design.json").write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown отчёт
    md = [f"# Дизайн-система `{design['domain']}`\n"]
    md.append(f"**URL:** {url}")
    md.append(f"**Title:** {info['title']}")
    md.append(f"**Language:** {info['lang']}\n")

    if css_extract["variables"]:
        md.append("## 🎨 CSS переменные\n")
        md.append("| Имя | Значение |")
        md.append("|---|---|")
        for name, val in list(css_extract["variables"].items())[:30]:
            md.append(f"| `--{name}` | `{val[:60]}` |")
        md.append("")

    if css_extract["colors"]:
        md.append("## 🎨 Топ-15 цветов (по частоте в CSS)\n")
        md.append("| # | Цвет | Использований | Превью |")
        md.append("|---|---|---|---|")
        for i, c in enumerate(css_extract["colors"][:15], 1):
            # placehold.co — действующий сервис превью (via.placeholder.com discontinued)
            preview = (
                f"![](https://placehold.co/40x20/{c['value'].lstrip('#')}/{c['value'].lstrip('#')}.png)"
                if c["value"].startswith("#") else "—"
            )
            md.append(f"| {i} | `{c['value']}` | {c['count']} | {preview} |")
        md.append("")

    if css_extract["fonts"]:
        md.append("## 🔤 Шрифты\n")
        md.append("| Семейство | Использований |")
        md.append("|---|---|")
        for f in css_extract["fonts"][:10]:
            md.append(f"| `{f['family']}` | {f['count']} |")
        md.append("")

    md.append("## 🖼 Ассеты\n")
    md.append(f"- Логотип: `{info['logo_url'] or '—'}`")
    md.append(f"- Favicon: `{info['favicon_url'] or '—'}`")
    md.append(f"- OG image: `{info['og_image'] or '—'}`")
    md.append("")

    md.append("---")
    md.append("🎨 *Згенеровано скілом [horoshop-design-extract](https://github.com/IgorShutko/horoshop-claude-skill) — Target+ Agency.*")

    Path("DESIGN_SYSTEM.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\n━━━ TL;DR ━━━")
    print(f"  Domain: {design['domain']}")
    print(f"  Цветов: {len(css_extract['colors'])}, переменных: {len(css_extract['variables'])}")
    print(f"  Шрифтов: {len(css_extract['fonts'])}")
    if css_extract["colors"][:5]:
        print(f"  Топ-5 цветов: {', '.join(c['value'] for c in css_extract['colors'][:5])}")
    if css_extract["fonts"][:3]:
        print(f"  Топ-3 шрифта: {', '.join(f['family'] for f in css_extract['fonts'][:3])}")
    print(f"\nФайлы: design.json, DESIGN_SYSTEM.md, assets/")


if __name__ == "__main__":
    main()

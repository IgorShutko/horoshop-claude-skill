#!/usr/bin/env python3
"""Аудит качества текстов в Horoshop.

Использование:
  python3 text_quality.py [--from-file catalog.json] [--lang ua]

Конфиг env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

BASE_URL = f"https://{DOMAIN}/api" if DOMAIN else None
EXPORT_BATCH = 100

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Text Quality)"})

_token = None
_token_time = 0


def get_token():
    global _token, _token_time
    if _token and (time.time() - _token_time) < 550:
        return _token
    r = session.post(f"{BASE_URL}/auth/", json={"login": LOGIN, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d["status"] != "OK":
        raise RuntimeError(d)
    _token = d["response"]["token"]
    _token_time = time.time()
    return _token


def export_catalog():
    products = []
    offset = 0
    while True:
        r = session.post(
            f"{BASE_URL}/catalog/export/",
            json={"token": get_token(), "offset": offset, "limit": EXPORT_BATCH},
            timeout=60,
        )
        r.raise_for_status()
        d = r.json()
        if d["status"] not in ("OK", "WARNING"):
            raise RuntimeError(d)
        batch = d["response"]["products"]
        if not batch:
            break
        products.extend(batch)
        if len(batch) < EXPORT_BATCH:
            break
        offset += EXPORT_BATCH
    return products


def get_text(field, lang):
    if not field:
        return ""
    if isinstance(field, dict):
        if "value" in field and isinstance(field["value"], dict):
            return field["value"].get(lang) or field["value"].get("ru") or ""
        return field.get(lang) or field.get("ru") or ""
    return str(field)


def strip_html(t):
    return re.sub(r"<[^>]+>", " ", t or "")


# ─── Паттерны ──────────────────────────────────────────────────────────────

# AI-стоп-слоп (русск. + укр.)
AI_SLOP_PHRASES = [
    "является", "представляет собой", "при этом", "по сути", "в целом",
    "буквально", "крайне", "весьма", "не просто",
    "стоит отметить", "хотелось бы", "следует отметить",
    "являє собою", "при цьому", "загалом", "буквально", "вкрай",
    "варто зазначити", "хотілось би",
]

# Маркетинг-вода
MARKETING_FLUFF = [
    "высочайшее качество", "непревзойденный", "уникальный", "инновационный",
    "передовой", "специально для вас", "именно для вашего комфорта",
    "найвища якість", "неперевершений", "унікальний", "інноваційний",
    "спеціально для вас", "саме для вашого комфорту", "лідер ринку",
]

# Дубли слов
DUP_WORDS_RE = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)

# Caps lock
CAPS_LOCK_RE = re.compile(r"\b[А-ЯЁІЇЄҐA-Z]{6,}\b")

# Дубли букв (в одном слове, например «оооочень»)
LETTER_DUP_RE = re.compile(r"(\w)\1{3,}", re.IGNORECASE)


def split_sentences(text):
    """Грубое разделение на предложения."""
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"[.!?]+\s+", text) if s.strip()]


def check_text(text):
    """Возвращает список проблем для одного текста."""
    issues = []
    if not text:
        return issues
    plain = strip_html(text).lower()
    plain_orig = strip_html(text)

    # AI-стоп-слоп
    found_slop = []
    for ph in AI_SLOP_PHRASES:
        if ph.lower() in plain:
            found_slop.append(ph)
    if found_slop:
        issues.append({"type": "ai_slop", "examples": found_slop[:3]})

    # Маркетинг-вода
    found_fluff = []
    for ph in MARKETING_FLUFF:
        if ph.lower() in plain:
            found_fluff.append(ph)
    if found_fluff:
        issues.append({"type": "marketing_fluff", "examples": found_fluff[:3]})

    # Дубли слов
    dups = DUP_WORDS_RE.findall(plain_orig)
    # Фильтр: исключаем валидные повторы типа "так-так" в кавычках, цифры, и т.д.
    dups = [d for d in dups if d.lower() not in ("так", "ну")]
    if dups:
        issues.append({"type": "duplicate_words", "examples": list(set(dups))[:3]})

    # CAPS LOCK слова
    caps = CAPS_LOCK_RE.findall(plain_orig)
    # Фильтр аббревиатур типа GTIN, MPN, USB
    caps = [c for c in caps if len(c) > 6 and c not in ("GTIN", "USB", "USA", "GMBH")]
    if caps:
        issues.append({"type": "caps_lock", "examples": list(set(caps))[:3]})

    # Дубли букв
    letter_dups = LETTER_DUP_RE.findall(plain_orig)
    if letter_dups:
        issues.append({"type": "letter_repeats", "examples": list(set(letter_dups))[:3]})

    # Длинные предложения
    sentences = split_sentences(plain_orig)
    long_sentences = [s for s in sentences if len(s.split()) > 35]
    if long_sentences:
        issues.append({
            "type": "long_sentence",
            "count": len(long_sentences),
            "example": long_sentences[0][:200] + "...",
        })

    return issues


def analyze(products, lang):
    findings = defaultdict(list)
    main = [p for p in products if p.get("article") == p.get("parent_article")]

    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title"), lang)

        texts = {
            "title": title,
            "description": get_text(p.get("description"), lang),
            "short_description": get_text(p.get("short_description"), lang),
            "marketplace_description": get_text(p.get("marketplace_description"), lang),
            "seo_title": get_text(p.get("seo_title"), lang),
            "seo_description": get_text(p.get("seo_description"), lang),
            "h1_title": get_text(p.get("h1_title"), lang),
        }

        product_issues = []
        for field_name, text in texts.items():
            if not text:
                continue
            field_issues = check_text(text)
            for issue in field_issues:
                issue["field"] = field_name
                product_issues.append(issue)

        if product_issues:
            findings["products_with_issues"].append({
                "article": article,
                "title": title,
                "issues": product_issues,
            })

    return findings, len(main)


def fmt_examples(items, n=3):
    if not items:
        return ""
    return ", ".join(f"`{x}`" for x in items[:n])


def generate_report(findings, total_main):
    md = []
    md.append(f"# Аудит якості текстів `{DOMAIN or 'локальний каталог'}`\n")
    md.append(f"**Головних товарів:** {total_main}\n")

    products = findings.get("products_with_issues", [])
    md.append(f"## 📊 Зведення\n")
    md.append(f"Товарів з проблемами в текстах: **{len(products)} / {total_main}** ({len(products)/total_main*100 if total_main else 0:.0f}%)\n")

    # Агрегация по типам
    by_type = Counter()
    by_field = Counter()
    for p in products:
        for iss in p["issues"]:
            by_type[iss["type"]] += 1
            by_field[iss["field"]] += 1

    if by_type:
        md.append("### За типом проблеми\n")
        md.append("| Тип | Кількість |")
        md.append("|---|---|")
        for t, c in by_type.most_common():
            md.append(f"| {t} | {c} |")
        md.append("")

    if by_field:
        md.append("### За полем\n")
        md.append("| Поле | Кількість проблем |")
        md.append("|---|---|")
        for f, c in by_field.most_common():
            md.append(f"| `{f}` | {c} |")
        md.append("")

    # Детали — топ-15 товаров с проблемами
    if products:
        md.append("## 🚨 Топ-15 товарів з найбільшою кількістю проблем\n")
        sorted_prods = sorted(products, key=lambda x: -len(x["issues"]))[:15]
        for p in sorted_prods:
            md.append(f"### `{p['article']}` — {p['title']}")
            for iss in p["issues"]:
                t = iss["type"]
                f = iss["field"]
                if t == "long_sentence":
                    md.append(f"- ⚠️ `{f}`: довге речення ({iss.get('count', 1)} шт). Приклад: «{iss.get('example', '')[:150]}...»")
                else:
                    examples = fmt_examples(iss.get("examples", []))
                    md.append(f"- ⚠️ `{f}` — **{t}**: {examples}")
            md.append("")

    md.append("\n## 💡 Що з цим робити\n")
    if by_type.get("ai_slop", 0) > 0:
        md.append(f"- **{by_type['ai_slop']} текстів з AI-стоп-слопом** — переписати без слів «являє собою», «при цьому», «варто зазначити». Або використай скіл `stop-slop` для масової чистки")
    if by_type.get("marketing_fluff", 0) > 0:
        md.append(f"- **{by_type['marketing_fluff']} текстів з маркетинг-водою** — замінити «найвища якість» на конкретні факти")
    if by_type.get("duplicate_words", 0) > 0:
        md.append(f"- **{by_type['duplicate_words']} текстів з повторами слів** — це баг вводу, прибрати руками")
    if by_type.get("long_sentence", 0) > 0:
        md.append(f"- **{by_type['long_sentence']} довгих речень** — розбити на 2-3 коротших для кращого скану")
    if by_type.get("caps_lock", 0) > 0:
        md.append(f"- **{by_type['caps_lock']} CAPS-слів** — текст «кричить» на читача, замінити на нормальний регістр")

    md.append("\n---\n")
    md.append("📝 *Згенеровано скілом [horoshop-text-quality](https://github.com/IgorShutko/horoshop-claude-skill) — Target+ Agency.*  ")
    md.append("*Допомога з переписуванням текстів? [TG @shutko_ads](https://t.me/shutko_ads).*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Horoshop text quality audit")
    parser.add_argument("--from-file", help="Каталог из локального JSON")
    parser.add_argument("--lang", default=LANG, help="Язык приоритетный (default ua)")
    args = parser.parse_args()

    if args.from_file:
        products = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    else:
        if not all([DOMAIN, LOGIN, PASSWORD]):
            print("ERROR: env not set", file=sys.stderr)
            sys.exit(1)
        print(f"=== Text quality {DOMAIN} ===\n[1/3] Выгрузка каталога...")
        products = export_catalog()
        Path("catalog.json").write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    print("[2/3] Анализ текстов...")
    findings, total_main = analyze(products, args.lang)
    Path("text_quality.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/3] Формирование TEXT_QUALITY_REPORT.md...")
    report = generate_report(findings, total_main)
    Path("TEXT_QUALITY_REPORT.md").write_text(report, encoding="utf-8")

    products_with_issues = findings.get("products_with_issues", [])
    print(f"\n━━━ TL;DR ━━━")
    print(f"  Главных товаров: {total_main}")
    print(f"  С проблемами в текстах: {len(products_with_issues)}")
    print(f"\nФайлы: TEXT_QUALITY_REPORT.md, text_quality.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Выбирает товары для psych-обогащения.

Использование:
  python3 find_targets.py [--from-file catalog.json]
                          [--discount-only] [--abc-only --abc-csv abc.csv]
                          [--limit 30]
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

BASE_URL = f"https://{DOMAIN}/api" if DOMAIN else None
EXPORT_BATCH = 100

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Marketing Psych)"})

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


def get_text(field, lang=LANG):
    if not field:
        return ""
    if isinstance(field, dict):
        if "value" in field and isinstance(field["value"], dict):
            return field["value"].get(lang) or field["value"].get("ru") or ""
        return field.get(lang) or field.get("ru") or ""
    return str(field)


def strip_html(t):
    return re.sub(r"<[^>]+>", " ", t or "")


def select_targets(products, args):
    main = [p for p in products if p.get("article") == p.get("parent_article")]
    candidates = []

    abc_a_articles = set()
    if args.abc_only and args.abc_csv:
        abc_path = Path(args.abc_csv)
        if abc_path.exists():
            with abc_path.open(encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("grade") == "A":
                        abc_a_articles.add(row.get("article"))

    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title"))
        if not article or not title:
            continue

        price = float(p.get("price") or 0)
        price_old = float(p.get("price_old") or 0)
        has_discount = price_old > price > 0

        # Фильтры
        if args.abc_only and article not in abc_a_articles:
            continue
        if args.discount_only and not has_discount:
            continue

        # Контекст для Claude
        chars = {}
        if isinstance(p.get("characteristics"), dict):
            for k, v in p["characteristics"].items():
                val = get_text(v) if isinstance(v, dict) else (str(v) if v else "")
                if val and val.strip():
                    chars[k] = val.strip()

        icons = []
        for ic in (p.get("icons") or []):
            if isinstance(ic, dict):
                v = ic.get("value", {})
                name = v.get("ua") or v.get("ru") or "" if isinstance(v, dict) else str(v)
            else:
                name = str(ic)
            if name:
                icons.append(name)

        candidates.append({
            "article": article,
            "title": title,
            "price": price,
            "price_old": price_old,
            "discount_pct": round((price_old - price) / price_old * 100, 1) if has_discount else 0,
            "has_discount": has_discount,
            "characteristics": chars,
            "icons_current": icons,
            "existing_short_description": strip_html(get_text(p.get("short_description")))[:300],
        })

    # Сортируем: A-товары и дисконты — первыми. Потом по выручке (если есть в abc.csv).
    candidates.sort(key=lambda x: (-x["has_discount"], -x["discount_pct"]))

    return candidates[:args.limit]


def main():
    parser = argparse.ArgumentParser(description="Find targets for psych enrichment")
    parser.add_argument("--from-file", help="Каталог из локального JSON")
    parser.add_argument("--discount-only", action="store_true")
    parser.add_argument("--abc-only", action="store_true")
    parser.add_argument("--abc-csv", default="abc.csv", help="Путь к ABC-анализу (default abc.csv)")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    if args.from_file:
        products = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    else:
        if not all([DOMAIN, LOGIN, PASSWORD]):
            print("ERROR: env not set", file=sys.stderr)
            sys.exit(1)
        print(f"=== Marketing psych targets {DOMAIN} ===\n[1/2] Выгрузка каталога...")
        products = export_catalog()
        Path("catalog.json").write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    print(f"[2/2] Выбор кандидатов (limit={args.limit}, abc_only={args.abc_only}, discount_only={args.discount_only})...")
    targets = select_targets(products, args)
    Path("targets.json").write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n━━━ TL;DR ━━━")
    print(f"  Кандидатов: {len(targets)}")
    if targets:
        print(f"  Со скидкой: {sum(1 for t in targets if t['has_discount'])}")
        print(f"\nДальше:")
        print(f"  Claude в чате должен прочитать targets.json + references/techniques.md")
        print(f"  И сгенерировать proposed_psych.json")
        print(f"  После — apply_psych.py --preview-only → apply_psych.py")
    print(f"\nФайл: targets.json")


if __name__ == "__main__":
    main()

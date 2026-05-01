#!/usr/bin/env python3
"""Сканирует каталог Хорошопа, находит товары с пустыми полями контента.

Использование:
  python3 find_gaps.py [--from-file catalog.json]
                       [--min-desc-len 200]
                       [--fields description,short_description,marketplace_description]

Конфиг через env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD, HOROSHOP_LANG (default ua)

Output:
  catalog.json (если выгружали из API)
  gaps.json — список товаров с пустыми полями + контекст для генерации
"""

import argparse
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
HTTP_TIMEOUT = 60

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Content Fill)"})

_token = None
_token_time = 0


def get_token():
    global _token, _token_time
    if _token and (time.time() - _token_time) < 550:
        return _token
    r = session.post(f"{BASE_URL}/auth/", json={"login": LOGIN, "password": PASSWORD}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    d = r.json()
    if d["status"] != "OK":
        raise RuntimeError(f"Auth failed: {d}")
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
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
        if d["status"] not in ("OK", "WARNING"):
            raise RuntimeError(f"Export error: {d}")
        batch = d["response"]["products"]
        if not batch:
            break
        products.extend(batch)
        print(f"  каталог: {len(products)}...", end="\r", flush=True)
        if len(batch) < EXPORT_BATCH:
            break
        offset += EXPORT_BATCH
    print(f"  каталог: {len(products)} товарів     ")
    return products


def get_text(field, lang=None):
    lang = lang or LANG
    if not field:
        return ""
    if isinstance(field, dict):
        if "value" in field and isinstance(field["value"], dict):
            return field["value"].get(lang) or field["value"].get("ru") or ""
        if "value" in field and isinstance(field["value"], str):
            return field["value"]
        return field.get(lang) or field.get("ru") or ""
    return str(field)


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def collect_characteristics(p):
    """Собрать заполненные характеристики в плоский dict."""
    out = {}
    chars = p.get("characteristics") or {}
    if not isinstance(chars, dict):
        return out
    for k, v in chars.items():
        val = get_text(v) if isinstance(v, dict) else (str(v) if v else "")
        if val and val.strip():
            out[k] = val.strip()
    return out


def find_gaps(products, fields, min_desc_len=200):
    """Возвращает список товаров с пустыми полями + контекст для генерации."""
    main = [p for p in products if p.get("article") == p.get("parent_article")]
    gaps = []
    counters = {f: 0 for f in fields}

    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title")).strip()
        if not article or not title:
            continue

        desc = strip_html(get_text(p.get("description")))
        short = strip_html(get_text(p.get("short_description")))
        mp = strip_html(get_text(p.get("marketplace_description")))

        gap_fields = []
        if "description" in fields:
            if not desc or len(desc) < min_desc_len:
                gap_fields.append("description")
                counters["description"] += 1
        if "short_description" in fields:
            if not short:
                gap_fields.append("short_description")
                counters["short_description"] += 1
        if "marketplace_description" in fields:
            if not mp:
                gap_fields.append("marketplace_description")
                counters["marketplace_description"] += 1

        if not gap_fields:
            continue

        # Контекст для генерации
        brand_obj = p.get("brand") or {}
        brand = get_text(brand_obj) if isinstance(brand_obj, dict) else str(brand_obj or "")
        parent = p.get("parent") or {}
        category = parent.get("value") if isinstance(parent, dict) else str(parent or "")
        if isinstance(category, dict):
            category = category.get(LANG) or category.get("ru") or ""

        item = {
            "article": article,
            "title": title,
            "brand": brand,
            "category": category,
            "price": p.get("price"),
            "price_old": p.get("price_old"),
            "currency": (p.get("currency") or {}).get("value") if isinstance(p.get("currency"), dict) else p.get("currency"),
            "characteristics": collect_characteristics(p),
            "existing_description": desc[:500] if desc else "",  # обрезаем для контекста
            "existing_description_full_length": len(desc) if desc else 0,
            "existing_short_description": short[:200] if short else "",
            "existing_marketplace_description": mp[:200] if mp else "",
            "gaps": gap_fields,
        }
        gaps.append(item)

    return gaps, counters


def main():
    parser = argparse.ArgumentParser(description="Find content gaps in Horoshop catalog")
    parser.add_argument("--from-file", help="Читать каталог из локального JSON вместо API")
    parser.add_argument("--min-desc-len", type=int, default=200, help="Порог длины description (default 200)")
    parser.add_argument(
        "--fields", default="description,short_description,marketplace_description",
        help="Какие поля проверять (через запятую)",
    )
    args = parser.parse_args()

    fields = [f.strip() for f in args.fields.split(",") if f.strip()]

    if args.from_file:
        print(f"Читаю каталог из {args.from_file}...")
        products = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    else:
        if not all([DOMAIN, LOGIN, PASSWORD]):
            print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы (или используй --from-file)", file=sys.stderr)
            sys.exit(1)
        print(f"=== Content gaps {DOMAIN} ===\n")
        print("[1/2] Выгрузка каталога...")
        products = export_catalog()
        Path("catalog.json").write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    print(f"[2/2] Поиск пустых полей (порог description: {args.min_desc_len} симв)...")
    gaps, counters = find_gaps(products, fields, args.min_desc_len)

    Path("gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")

    main_count = sum(1 for p in products if p.get("article") == p.get("parent_article"))
    print(f"\n━━━ TL;DR ━━━")
    print(f"  Главных товаров: {main_count}")
    for f in fields:
        print(f"  Пустых {f}: {counters.get(f, 0)}")
    print(f"  → Всего товаров с пустыми полями: {len(gaps)}")
    print(f"\nФайлы: gaps.json (контекст для Claude-генерации)")
    if gaps:
        print(f"\nПример первого товара с пробелами:")
        ex = gaps[0]
        print(f"  article: {ex['article']}")
        print(f"  title: {ex['title']}")
        print(f"  gaps: {ex['gaps']}")
        print(f"  characteristics: {list(ex['characteristics'].keys())}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Применяет сгенерированный контент к товарам через `catalog/import`.

Использование:
  # Сначала превью
  python3 apply_content.py --preview-only

  # После одобрения
  python3 apply_content.py [--input proposed_content.json] [--limit N]

Формат `proposed_content.json` (создаётся Claude'ом в основном чате):
  [
    {
      "article": "1234",
      "description": "<p>...</p><h2>...</h2>...",
      "short_description": "...",
      "marketplace_description": "..."
    },
    ...
  ]

Конфиг через env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD, HOROSHOP_LANG
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

BASE_URL = f"https://{DOMAIN}/api" if DOMAIN else None
IMPORT_BATCH = 50
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


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def truncate(s, n):
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n - 1] + "…"


def show_preview(updates, gaps_path="gaps.json", limit=5):
    """Показывает diff текущего и нового для первых N товаров."""
    # Подгружаем gaps.json чтобы видеть исходное состояние
    existing = {}
    if Path(gaps_path).exists():
        gaps = json.loads(Path(gaps_path).read_text(encoding="utf-8"))
        for g in gaps:
            existing[g["article"]] = g
    else:
        print(f"⚠ {gaps_path} не найден — будет показан только новый контент без diff")

    print(f"\n━━━ ПРЕВЬЮ (первые {min(limit, len(updates))} из {len(updates)}) ━━━\n")
    for i, u in enumerate(updates[:limit], 1):
        article = u.get("article")
        ex = existing.get(article, {})
        print(f"#{i}  Article: {article}")
        print(f"    Title:   {ex.get('title', '?')}")
        print(f"    Бренд:   {ex.get('brand', '—')}  Категория: {ex.get('category', '—')}")
        print(f"    Чеки:    {ex.get('price', '?')} грн (старая: {ex.get('price_old', '—')})")
        print(f"    Хар-ки:  {', '.join(ex.get('characteristics', {}).keys())}")
        print()
        for field in ("description", "short_description", "marketplace_description"):
            if field not in u:
                continue
            new_val = u[field]
            new_text = strip_html(new_val) if isinstance(new_val, str) else strip_html(str(new_val))
            old_len = (
                ex.get(f"existing_{field}_full_length") if field == "description"
                else len(ex.get(f"existing_{field}", ""))
            )
            print(f"    📝 {field}:")
            print(f"       Было: {old_len} симв  →  Стало: {len(new_text)} симв")
            preview_text = truncate(new_text, 280)
            indent = "       "
            for line in preview_text.split("\n"):
                print(f"{indent}{line}")
            print()
        print("─" * 60)


def normalize_update(u):
    """Превращает плоский dict {article, description, short_description, ...}
    в формат `catalog/import` с lang-обёрткой."""
    out = {"article": u["article"]}
    for fld in ("description", "short_description", "marketplace_description",
                "seo_title", "seo_description", "seo_keywords", "h1_title", "title",
                "mod_title"):
        if fld in u and u[fld]:
            val = u[fld]
            if isinstance(val, str):
                out[fld] = {LANG: val}
            elif isinstance(val, dict):
                out[fld] = val  # уже мультиязычное
    return out


def import_products(updates, dry_run=False):
    """Пакетный импорт через catalog/import."""
    if dry_run:
        print(f"\n[DRY RUN] Будет обновлено {len(updates)} товаров (без записи)")
        return len(updates), []

    print(f"\nИмпорт {len(updates)} товаров батчами по {IMPORT_BATCH}...")
    ok, errors = 0, []
    for i in range(0, len(updates), IMPORT_BATCH):
        batch = updates[i:i + IMPORT_BATCH]
        normalized = [normalize_update(u) for u in batch]
        r = session.post(
            f"{BASE_URL}/catalog/import/",
            json={"token": get_token(), "products": normalized},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        result = r.json()
        for log_item in result.get("response", {}).get("log", []):
            codes = [x["code"] for x in log_item.get("info", [])]
            if 0 in codes:
                ok += 1
            else:
                errors.append({"article": log_item["article"], "info": log_item["info"]})
        print(f"  {min(i+IMPORT_BATCH, len(updates))}/{len(updates)}", end="\r", flush=True)

    print(f"\nОК: {ok}, ошибок: {len(errors)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"fix_content_{ts}.json")
    log_path.write_text(json.dumps({
        "timestamp": ts, "ok": ok, "errors": errors,
        "updates_sent": [normalize_update(u) for u in updates],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Лог: {log_path}")

    if errors:
        codes = []
        for it in errors[:5]:
            codes.extend([x["code"] for x in it.get("info", [])])
        if 11 in codes:
            print("\n⚠ Код 11: одно из полей не в шаблоне «Каталог».")
            print("  Включи в админке: Налаштування → Система → Каталог → Шаблон даних")

    return ok, errors


def main():
    parser = argparse.ArgumentParser(description="Apply generated content to Horoshop")
    parser.add_argument("--input", default="proposed_content.json", help="Файл со сгенерированным контентом")
    parser.add_argument("--gaps", default="gaps.json", help="Файл с исходным состоянием (для diff)")
    parser.add_argument("--preview-only", action="store_true", help="Только показать diff, без записи")
    parser.add_argument("--dry-run", action="store_true", help="Запросить confirmation, но не писать")
    parser.add_argument("--limit", type=int, default=5, help="Кол-во товаров в превью (default 5)")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: {args.input} не найден.", file=sys.stderr)
        print("Сначала запусти find_gaps.py, потом попроси Claude сгенерировать тексты в proposed_content.json.", file=sys.stderr)
        sys.exit(1)

    updates = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(updates, list) or not updates:
        print(f"ERROR: {args.input} должен быть непустым массивом объектов с article и контентом", file=sys.stderr)
        sys.exit(1)

    show_preview(updates, args.gaps, args.limit)

    if args.preview_only:
        print("\n[--preview-only] Запись пропущена. Запусти без флага для импорта.")
        return

    if not all([DOMAIN, LOGIN, PASSWORD]) and not args.dry_run:
        print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run:
        ans = input(f"\nЗаписать {len(updates)} обновлений в {DOMAIN}? (y/N): ").strip().lower()
        if ans != "y":
            print("Отменено.")
            return

    import_products(updates, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

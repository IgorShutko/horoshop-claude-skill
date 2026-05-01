#!/usr/bin/env python3
"""Применяет psych-обогащённый контент через catalog/import.

Использование:
  python3 apply_psych.py --preview-only
  python3 apply_psych.py [--input proposed_psych.json]

Формат `proposed_psych.json`:
  [
    {
      "article": "...",
      "techniques_applied": ["scarcity", "social_proof"],
      "description": "<HTML>",
      "short_description": "...",
      "icons": ["Хіт продажів", "Залишилось 3 шт"]
    }
  ]
"""

import argparse
import json
import os
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


def normalize_update(u):
    """Превращает {article, description, short_description, icons} в формат API."""
    out = {"article": u["article"]}
    for fld in ("description", "short_description", "marketplace_description", "h1_title"):
        if fld in u and u[fld]:
            v = u[fld]
            out[fld] = {LANG: v} if isinstance(v, str) else v
    if "icons" in u:
        out["icons"] = u["icons"]
    return out


def show_preview(updates, targets_path="targets.json", limit=5):
    targets_map = {}
    if Path(targets_path).exists():
        for t in json.loads(Path(targets_path).read_text(encoding="utf-8")):
            targets_map[t["article"]] = t

    print(f"\n━━━ ПРЕВЬЮ (первые {min(limit, len(updates))} из {len(updates)}) ━━━\n")
    for i, u in enumerate(updates[:limit], 1):
        article = u["article"]
        t = targets_map.get(article, {})
        print(f"#{i}  Article: {article}")
        print(f"    Title:   {t.get('title', '?')}")
        print(f"    Скидка:  {t.get('discount_pct', 0)}%  ({t.get('price_old', '—')} → {t.get('price', '—')})")
        print(f"    Применено: {', '.join(u.get('techniques_applied', []))}")
        if "icons" in u:
            print(f"    Стикеры (новые): {', '.join(u['icons'])}")
        if "short_description" in u:
            print(f"    short_desc:  {u['short_description'][:160]}")
        if "description" in u:
            import re
            desc_text = re.sub(r"<[^>]+>", " ", u["description"])
            print(f"    description (превью): {desc_text[:200]}...")
        print("─" * 60)


def import_batch(updates):
    print(f"\nИмпорт {len(updates)} товаров батчами по {IMPORT_BATCH}...")
    ok, errors = 0, []
    for i in range(0, len(updates), IMPORT_BATCH):
        batch = updates[i:i+IMPORT_BATCH]
        normalized = [normalize_update(u) for u in batch]
        r = session.post(
            f"{BASE_URL}/catalog/import/",
            json={"token": get_token(), "products": normalized},
            timeout=60,
        )
        r.raise_for_status()
        result = r.json()
        for log_item in result.get("response", {}).get("log", []):
            codes = [x["code"] for x in log_item.get("info", [])]
            if 0 in codes:
                ok += 1
            else:
                errors.append({"article": log_item["article"], "info": log_item["info"]})

    print(f"OK: {ok}, ошибок: {len(errors)}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(f"fix_psych_{ts}.json").write_text(json.dumps({
        "ok": ok, "errors": errors,
        "updates_sent": [normalize_update(u) for u in updates],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return ok, errors


def main():
    parser = argparse.ArgumentParser(description="Apply psych-enriched content")
    parser.add_argument("--input", default="proposed_psych.json")
    parser.add_argument("--targets", default="targets.json")
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: {args.input} не найден. Сначала запусти find_targets.py и попроси Claude сгенерировать proposed_psych.json", file=sys.stderr)
        sys.exit(1)

    updates = json.loads(Path(args.input).read_text(encoding="utf-8"))
    show_preview(updates, args.targets)

    if args.preview_only:
        print("\n[--preview-only] Запись пропущена.")
        return

    if not all([DOMAIN, LOGIN, PASSWORD]):
        print("ERROR: env not set", file=sys.stderr)
        sys.exit(1)

    ans = input(f"\nЗаписать {len(updates)} обновлений в {DOMAIN}? (y/N): ").strip().lower()
    if ans != "y":
        print("Отменено.")
        return

    import_batch(updates)


if __name__ == "__main__":
    main()

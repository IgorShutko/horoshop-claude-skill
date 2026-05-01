#!/usr/bin/env python3
"""Horoshop full audit — применение API-фиксов.

Использование:
  python3 apply_fixes.py --fix <name> [--dry-run] [--preview-only]

Доступные фиксы (см. references/fix_recipes.md):
  countdown        — обнуление истёкших countdown_end_time
  mod-title        — заполнение mod_title из ключевой характеристики
  discount         — пересчёт discount по price/price_old
  seo              — заполнение пустых SEO-полей (с превью)
  mpn              — генерация mpn по шаблону <PREFIX>-<article>
  dup-desc         — переписывание дубликатов description (с превью)
  installments     — включение оплаты частями Privat + Monobank
  sticker-sale     — добавление стикера Распродажа в icons
  inline-styles    — очистка inline-стилей в описаниях (с превью)
  cross-sell       — настройка accessories/alt_parent (interactive)

Конфиг через env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD, HOROSHOP_LANG (default ua)

Все скрипты:
- Пишут лог fix_<name>_<timestamp>.json
- Поддерживают --dry-run
- Не перезаписывают непустые значения, кроме явных случаев
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

if not all([DOMAIN, LOGIN, PASSWORD]):
    print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы", file=sys.stderr)
    sys.exit(1)

BASE_URL = f"https://{DOMAIN}/api"
IMPORT_BATCH = 50
HTTP_TIMEOUT = 60

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop SEO Fix)"})

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


def get_text(field, lang=LANG):
    if not field:
        return ""
    if isinstance(field, dict):
        if "value" in field and isinstance(field["value"], dict):
            return field["value"].get(lang) or field["value"].get("ru") or ""
        if "value" in field and isinstance(field["value"], str):
            return field["value"]
        return field.get(lang) or field.get("ru") or ""
    return str(field)


def import_products(updates, dry_run=False, fix_name="fix"):
    """Пакетный импорт. updates = [{article, ...поля...}]. Возвращает (ok, errors)."""
    if dry_run:
        print(f"\n[DRY RUN] Будет обновлено {len(updates)} товаров. Первые 5:")
        for u in updates[:5]:
            print(f"  {json.dumps(u, ensure_ascii=False)[:300]}")
        return len(updates), []

    print(f"\nИмпорт {len(updates)} товаров батчами по {IMPORT_BATCH}...")
    ok, errors = 0, []
    for i in range(0, len(updates), IMPORT_BATCH):
        batch = updates[i:i+IMPORT_BATCH]
        r = session.post(
            f"{BASE_URL}/catalog/import/",
            json={"token": get_token(), "products": batch},
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

    # Лог
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"fix_{fix_name}_{ts}.json")
    log_path.write_text(json.dumps({
        "fix": fix_name,
        "timestamp": ts,
        "ok": ok,
        "errors": errors,
        "updates_sent": updates,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Лог: {log_path}")

    if errors:
        # Проверим частые причины
        codes = [item["info"][0]["code"] for item in errors[:5] if item.get("info")]
        if 11 in codes:
            print("\n⚠ Код 11: поле не найдено в шаблоне Каталог. В админке: Налаштування → Система → Каталог → Шаблон даних")

    return ok, errors


def load_findings():
    """Загружаем findings.json (создаётся audit.py)."""
    path = Path("findings.json")
    if not path.exists():
        print("ERROR: findings.json не найден. Сначала запусти audit.py", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog():
    path = Path("catalog.json")
    if not path.exists():
        print("ERROR: catalog.json не найден. Сначала запусти audit.py", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


# ─── Fix 1: countdown ────────────────────────────────────────────────────

def fix_countdown(args):
    f = load_findings()
    expired = f["findings"].get("countdown_expired", [])
    if not expired:
        print("Истёкших таймеров не найдено.")
        return

    new_value = ""
    if args.extend_days:
        new_dt = datetime.now() + timedelta(days=int(args.extend_days))
        new_value = new_dt.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Продлеваем все таймеры на {args.extend_days} дней → {new_value}")
    else:
        print("Обнуляем countdown_end_time у всех истёкших.")

    updates = [{"article": e["article"], "countdown_end_time": new_value} for e in expired]
    import_products(updates, dry_run=args.dry_run, fix_name="countdown")


# ─── Fix 2: mod-title ────────────────────────────────────────────────────

def fix_mod_title(args):
    products = load_catalog()
    by_parent = {}
    for p in products:
        by_parent.setdefault(p.get("parent_article", ""), []).append(p)

    updates = []
    preview = []
    for parent_a, group in by_parent.items():
        mains = [g for g in group if g.get("article") == g.get("parent_article")]
        mods = [g for g in group if g.get("article") != g.get("parent_article")]
        if not mods:
            continue
        # Какие характеристики отличаются?
        char_values = {}
        for m in mods:
            chars = m.get("characteristics") or {}
            for k, v in chars.items():
                val = get_text(v) if isinstance(v, dict) else (str(v) if v else "")
                char_values.setdefault(k, set()).add(val)
            # rozmr — отдельное поле верхнего уровня
            rozmr = m.get("rozmr") or {}
            if isinstance(rozmr, dict):
                rv = get_text(rozmr)
                if rv:
                    char_values.setdefault("rozmr", set()).add(rv)

        differing = [k for k, vs in char_values.items() if len(vs) > 1 and "" not in vs]

        if not differing:
            continue

        # Используем первое отличающееся (приоритет: rozmr > kolr > materal > другое)
        priority_keys = ["rozmr", "size", "kolr", "color", "materal", "material"]
        chosen = None
        for pk in priority_keys:
            if pk in differing:
                chosen = pk
                break
        if not chosen:
            chosen = differing[0]

        for m in mods:
            current_mt = get_text(m.get("mod_title")).strip()
            if current_mt:
                continue
            # Получаем значение
            if chosen == "rozmr":
                val = get_text(m.get("rozmr"))
            else:
                chars = m.get("characteristics") or {}
                v = chars.get(chosen)
                val = get_text(v) if isinstance(v, dict) else (str(v) if v else "")
            if not val:
                continue
            updates.append({"article": m["article"], "mod_title": {LANG: val}})
            if len(preview) < 10:
                preview.append({"article": m["article"], "parent": parent_a, "mod_title": val, "via": chosen})

    if not updates:
        print("Нечего обновлять — модификации либо имеют mod_title, либо нет различающих характеристик.")
        return

    print(f"\nПревью первых 10 (всего {len(updates)}):")
    for p in preview:
        print(f"  [{p['article']}] (parent {p['parent']}) → '{p['mod_title']}' (via {p['via']})")

    if not args.dry_run:
        ans = input("\nПродолжить? (y/N): ").strip().lower()
        if ans != "y":
            print("Отменено.")
            return

    import_products(updates, dry_run=args.dry_run, fix_name="mod_title")


# ─── Fix 3: discount ─────────────────────────────────────────────────────

def fix_discount(args):
    f = load_findings()
    items = f["findings"].get("discount_unmarked", [])
    if not items:
        print("Товаров с непомеченной скидкой не найдено.")
        return

    updates = []
    for it in items:
        d = round(it["real_discount"])
        updates.append({"article": it["article"], "discount": d})

    print(f"Обновим discount у {len(updates)} товаров. Первые 5:")
    for it in items[:5]:
        print(f"  [{it['article']}] {it['title']}: {it['price']}/{it['price_old']} → {round(it['real_discount'])}%")

    import_products(updates, dry_run=args.dry_run, fix_name="discount")


# ─── Fix 4: seo (с превью) ───────────────────────────────────────────────

def _build_seo(product):
    title = get_text(product.get("title"))
    chars = product.get("characteristics") or {}
    color = get_text(chars.get("kolr") or chars.get("color") or product.get("color"))
    material = get_text(chars.get("materal") or chars.get("material"))
    brand = get_text(product.get("brand"))
    parent = product.get("parent") or {}
    cat_name = parent.get("value") if isinstance(parent, dict) else ""

    seo_title = f"{title}"
    if brand and brand not in seo_title:
        seo_title += f" — {brand}"
    seo_title += " | купити з доставкою"
    seo_title = seo_title[:70]

    short = get_text(product.get("short_description"))
    short_text = re.sub(r"<[^>]+>", "", short).strip()[:80]
    seo_desc = title
    if color:
        seo_desc += f" {color}"
    if material:
        seo_desc += f" з {material.lower()}"
    if short_text:
        seo_desc += f". {short_text}"
    seo_desc = seo_desc[:160]

    seo_kw_parts = [title.lower()]
    if cat_name:
        seo_kw_parts.append(cat_name.lower())
    if color:
        seo_kw_parts.append(color.lower())
    if cat_name:
        seo_kw_parts.append(f"купити {cat_name.lower()}")
    seo_keys = ", ".join(seo_kw_parts)[:200]

    h1 = title

    return {
        "seo_title": {LANG: seo_title},
        "seo_description": {LANG: seo_desc},
        "seo_keywords": {LANG: seo_keys},
        "h1_title": {LANG: h1},
    }


def fix_seo(args):
    products = load_catalog()
    main = [p for p in products if p.get("article") == p.get("parent_article")]

    candidates = []
    for p in main:
        empty_fields = []
        for fld in ["seo_title", "seo_description", "seo_keywords", "h1_title"]:
            if not get_text(p.get(fld)).strip():
                empty_fields.append(fld)
        if empty_fields:
            candidates.append((p, empty_fields))

    if not candidates:
        print("Все товары имеют SEO-поля.")
        return

    print(f"\nКандидатов на заполнение: {len(candidates)}")
    print("\nПревью первых 5 (текущее → предложенное):\n")
    updates = []
    for p, empty in candidates:
        suggested = _build_seo(p)
        update = {"article": p["article"]}
        for fld in empty:
            update[fld] = suggested[fld]
        updates.append(update)

    for p, empty in candidates[:5]:
        print(f"  [{p['article']}] {get_text(p.get('title'))}")
        suggested = _build_seo(p)
        for fld in empty:
            print(f"    {fld}: '' → '{get_text(suggested[fld])}'")
        print()

    if args.preview_only:
        out = Path(f"seo_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        out.write_text(json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Превью сохранено: {out}")
        return

    if not args.dry_run:
        ans = input(f"\nЗаписать {len(updates)} обновлений? (y/N): ").strip().lower()
        if ans != "y":
            print("Отменено.")
            return

    import_products(updates, dry_run=args.dry_run, fix_name="seo")


# ─── Fix 5: mpn ──────────────────────────────────────────────────────────

def fix_mpn(args):
    products = load_catalog()
    main = [p for p in products if p.get("article") == p.get("parent_article")]

    prefix = args.prefix
    if not prefix:
        # Из бренда
        brands = set()
        for p in main:
            b = get_text(p.get("brand"))
            if b:
                brands.add(b)
        if len(brands) == 1:
            b = brands.pop()
            prefix = "".join(c for c in b if c.isupper())[:4]
            if len(prefix) < 2:
                prefix = b[:3].upper()
            print(f"Префикс из бренда '{b}': {prefix}")
        else:
            print("ERROR: укажите --prefix (несколько брендов в каталоге)", file=sys.stderr)
            sys.exit(1)

    updates = []
    for p in main:
        if (p.get("mpn") or "").strip():
            continue
        mpn = f"{prefix}-{p['article']}"
        updates.append({"article": p["article"], "mpn": mpn})

    if not updates:
        print("Все товары имеют MPN.")
        return

    print(f"\nЗапишем MPN для {len(updates)} товаров. Шаблон: {prefix}-<article>")
    print("Первые 5:")
    for u in updates[:5]:
        print(f"  [{u['article']}] mpn = {u['mpn']}")

    import_products(updates, dry_run=args.dry_run, fix_name="mpn")


# ─── Fix 6: dup-desc ─────────────────────────────────────────────────────

def fix_dup_desc(args):
    f = load_findings()
    dups = f["findings"].get("dup_description", [])
    if not dups:
        print("Дубликатов description не найдено.")
        return

    print(f"Найдено {len(dups)} групп дубликатов. Покажу превью.\n")
    for d in dups[:5]:
        print(f"  Дубль ({len(d['articles'])} товаров): {d['articles']}")
        print(f"    Текст: {d['value'][:120]}...\n")

    print("⚠️ Этот фикс требует обсуждения стратегии:")
    print("   Стратегия А — вариативная замена цвета/материала в общем шаблоне")
    print("   Стратегия Б — генерация уникальных текстов под каждый товар (нужна Claude)")
    print("\nДля стратегии Б — попроси Claude сгенерировать уникальные тексты,")
    print("сохранить их в proposed_descriptions.json в формате:")
    print('  [{"article": "1248", "description": {"ua": "<HTML>..."}}, ...]')
    print("\nЗатем запусти:")
    print(f"  python3 apply_fixes.py --fix dup-desc --import-file proposed_descriptions.json")

    if args.import_file:
        path = Path(args.import_file)
        if not path.exists():
            print(f"ERROR: файл {args.import_file} не найден")
            return
        updates = json.loads(path.read_text(encoding="utf-8"))
        print(f"\nЗагружено {len(updates)} обновлений из {args.import_file}")
        if not args.dry_run:
            ans = input("Записать? (y/N): ").strip().lower()
            if ans != "y":
                return
        import_products(updates, dry_run=args.dry_run, fix_name="dup_desc")


# ─── Fix 7: installments ─────────────────────────────────────────────────

def fix_installments(args):
    f = load_findings()
    items = f["findings"].get("installments_disabled", [])
    if not items:
        print("Все товары имеют включённую оплату частями.")
        return

    updates = []
    for it in items:
        updates.append({
            "article": it["article"],
            "installments_payment": {"id": 2},
            "monobank_installments_payment": {"id": 2},
        })

    print(f"Включим оплату частями (Privat + Monobank) для {len(updates)} товаров.")
    print("Если в админке функция не активирована — API вернёт код 11 (поле не в шаблоне).")
    print("Тогда: Налаштування → Система → Каталог → Шаблон даних → активувати.")

    import_products(updates, dry_run=args.dry_run, fix_name="installments")


# ─── Fix 8: sticker-sale ─────────────────────────────────────────────────

def fix_sticker_sale(args):
    products = load_catalog()
    f = load_findings()
    items = f["findings"].get("no_sale_sticker", [])
    if not items:
        print("Все товары со скидкой имеют стикер.")
        return

    by_article = {p["article"]: p for p in products}
    sticker_name = args.sticker_name or "Распродажа"

    updates = []
    for it in items:
        article = it["article"]
        p = by_article.get(article)
        if not p:
            continue
        existing = p.get("icons") or []
        existing_names = []
        for ic in existing:
            v = ic.get("value", {}) if isinstance(ic, dict) else {}
            n = v.get("ua") or v.get("ru") or "" if isinstance(v, dict) else str(v)
            if n:
                existing_names.append(n)
        new_icons = existing_names + [sticker_name]
        updates.append({"article": article, "icons": new_icons})

    print(f"Добавим стикер «{sticker_name}» для {len(updates)} товаров.")
    print("Если стикер не существует в наборе магазина — Хорошоп его проигнорирует или создаст.")

    import_products(updates, dry_run=args.dry_run, fix_name="sticker_sale")


# ─── Fix 9: inline-styles ────────────────────────────────────────────────

KEY_HEADINGS = ["Догляд", "Особливості", "Розмір", "Доставка", "Склад", "Характеристики", "Преимущества", "Уход"]


def _clean_html(html):
    # Убираем style="..." атрибуты
    html = re.sub(r'\s*style\s*=\s*"[^"]*"', '', html)
    # Поднимаем смысловые подзаголовки до h2
    for kw in KEY_HEADINGS:
        # <p>Догляд</p> или <span>Догляд</span> или <strong>Догляд</strong>
        html = re.sub(
            rf'<(p|span|strong|b)[^>]*>\s*({re.escape(kw)})\s*</\1>',
            r'<h2>\2</h2>',
            html,
            flags=re.IGNORECASE,
        )
    return html


def fix_inline_styles(args):
    products = load_catalog()
    main = [p for p in products if p.get("article") == p.get("parent_article")]

    updates = []
    previews = []
    for p in main:
        original = get_text(p.get("description"))
        if not original:
            continue
        styles_count = len(re.findall(r'style\s*=\s*"[^"]+"', original))
        if styles_count <= 5:
            continue
        cleaned = _clean_html(original)
        if cleaned == original:
            continue
        updates.append({"article": p["article"], "description": {LANG: cleaned}})
        if len(previews) < 3:
            previews.append({
                "article": p["article"],
                "title": get_text(p.get("title")),
                "before_styles": styles_count,
                "before_sample": original[:300],
                "after_sample": cleaned[:300],
            })

    if not updates:
        print("Нечего чистить.")
        return

    print(f"\nКандидатов на чистку: {len(updates)}")
    print("\nПревью первых 3 (before → after):\n")
    for pv in previews:
        print(f"[{pv['article']}] {pv['title']}")
        print(f"  inline-стилей: {pv['before_styles']}")
        print(f"  ДО:    {pv['before_sample'][:200]}")
        print(f"  ПОСЛЕ: {pv['after_sample'][:200]}")
        print()

    if args.preview_only:
        out = Path(f"inline_styles_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        out.write_text(json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Превью сохранено: {out}")
        return

    if not args.dry_run:
        ans = input(f"\nОбновить {len(updates)} описаний? (y/N): ").strip().lower()
        if ans != "y":
            return

    import_products(updates, dry_run=args.dry_run, fix_name="inline_styles")


# ─── Fix 10: cross-sell (interactive) ────────────────────────────────────

def fix_cross_sell(args):
    f = load_findings()
    no_acc = f["findings"].get("no_accessories", [])
    no_alt = f["findings"].get("no_alt_parent", [])

    print(f"\nТоваров без accessories: {len(no_acc)}")
    print(f"Товаров без alt_parent: {len(no_alt)}\n")

    print("Этот фикс требует стратегии — что и куда привязывать.")
    print("Варианты:")
    print("  1. accessories по категориям: к каждому товару привязать категории-аксессуары")
    print("     Например: к комплекту белья → 'Простирадла', 'Подушки'")
    print("  2. alt_parent для топ-N: товары с popularity ≥ X → в раздел 'Хіти'")
    print()
    print("Чтобы применить — попроси Claude составить список accessories_strategy.json:")
    print('  [{"article": "1248", "accessories": [{"page": "Простирадла на гумці"}, {"page": "Подушки"}]}, ...]')
    print()
    print("После — запусти:")
    print(f"  python3 apply_fixes.py --fix cross-sell --import-file accessories_strategy.json")

    if args.import_file:
        path = Path(args.import_file)
        if not path.exists():
            print(f"ERROR: файл {args.import_file} не найден")
            return
        updates = json.loads(path.read_text(encoding="utf-8"))
        print(f"\nЗагружено {len(updates)} обновлений")
        if not args.dry_run:
            ans = input("Записать? (y/N): ").strip().lower()
            if ans != "y":
                return
        import_products(updates, dry_run=args.dry_run, fix_name="cross_sell")


# ─── CLI ─────────────────────────────────────────────────────────────────

DISPATCH = {
    "countdown": fix_countdown,
    "mod-title": fix_mod_title,
    "discount": fix_discount,
    "seo": fix_seo,
    "mpn": fix_mpn,
    "dup-desc": fix_dup_desc,
    "installments": fix_installments,
    "sticker-sale": fix_sticker_sale,
    "inline-styles": fix_inline_styles,
    "cross-sell": fix_cross_sell,
}


def main():
    parser = argparse.ArgumentParser(description="Horoshop API fixes")
    parser.add_argument("--fix", required=True, choices=list(DISPATCH.keys()))
    parser.add_argument("--dry-run", action="store_true", help="показать что будет изменено без записи")
    parser.add_argument("--preview-only", action="store_true", help="только сохранить preview JSON, без подтверждения и без записи")
    parser.add_argument("--extend-days", type=int, help="(countdown) продлить на N дней вместо обнуления")
    parser.add_argument("--prefix", help="(mpn) префикс для генерации MPN")
    parser.add_argument("--sticker-name", help="(sticker-sale) имя стикера, по умолчанию 'Распродажа'")
    parser.add_argument("--import-file", help="(dup-desc, cross-sell) JSON-файл с готовыми обновлениями")
    args = parser.parse_args()

    DISPATCH[args.fix](args)


if __name__ == "__main__":
    main()

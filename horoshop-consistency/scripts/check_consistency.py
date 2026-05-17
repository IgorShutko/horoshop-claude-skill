#!/usr/bin/env python3
"""Поиск противоречий между текстом описания и characteristics.

Использование:
  python3 check_consistency.py [--from-file catalog.json]
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

BASE_URL = f"https://{DOMAIN}/api" if DOMAIN else None
EXPORT_BATCH = 100

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Consistency)"})

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


# ─── Словари ───────────────────────────────────────────────────────────────

# Материалы (UA + RU + транслит)
MATERIALS = {
    "бавовна": ["бавовна", "хлопок", "cotton", "бавовняний", "хлопковый"],
    "поліестер": ["поліестер", "полиэстер", "polyester"],
    "сатин": ["сатин"],
    "мікросатин": ["мікросатин", "микросатин"],
    "лен": ["лен", "льон"],
    "шерсть": ["шерсть", "вовна"],
    "шкіра": ["шкіра", "кожа", "leather", "шкіряний"],
    "силікон": ["силікон", "силикон", "silicone"],
    "пластик": ["пластик", "plastic"],
    "метал": ["метал", "металл", "metal"],
    "холлофайбер": ["холлофайбер", "холлофайбер"],
    "велюр": ["велюр"],
    "оксфорд": ["оксфорд"],
}

# Страны
COUNTRIES = {
    "україна": ["україна", "украина", "ukrainian", "український", "украинский"],
    "польща": ["польща", "польша", "poland", "польский"],
    "китай": ["китай", "china", "chinese", "китайский"],
    "туреччина": ["туреччина", "турция", "turkey", "turkish", "турецкий"],
    "італія": ["італія", "италия", "italy", "italian"],
    "німеччина": ["німеччина", "германия", "germany", "german"],
    "сша": ["сша", "usa", "америка"],
    "індія": ["індія", "индия", "india"],
}

# Цвета
COLORS = {
    "чорний": ["чорний", "черный", "black"],
    "білий": ["білий", "белый", "white"],
    "червоний": ["червоний", "красный", "red"],
    "синій": ["синій", "синий", "blue"],
    "зелений": ["зелений", "зеленый", "green"],
    "жовтий": ["жовтий", "желтый", "yellow"],
    "сірий": ["сірий", "серый", "grey", "gray"],
    "коричневий": ["коричневий", "коричневый", "brown"],
    "рожевий": ["рожевий", "розовый", "pink"],
    "фіолетовий": ["фіолетовий", "фиолетовый", "purple"],
}


def detect_in_text(text, dictionary):
    """Возвращает set найденных канонических ключей."""
    text_l = text.lower()
    found = set()
    for canonical, variants in dictionary.items():
        for v in variants:
            # Используем word boundary где возможно
            if re.search(r"\b" + re.escape(v) + r"\b", text_l):
                found.add(canonical)
                break
    return found


def get_char_value(p, char_keys):
    """Достаёт первое непустое значение из characteristics для одного из ключей."""
    chars = p.get("characteristics") or {}
    if not isinstance(chars, dict):
        return None
    for k in char_keys:
        if k in chars:
            v = chars[k]
            val = get_text(v) if isinstance(v, dict) else (str(v) if v else "")
            if val and val.strip():
                return val.strip().lower()
    return None


def get_top_level_value(p, key):
    """Для полей вне characteristics (color — top-level в Horoshop API).

    На экспорте формат: {"id": N, "value": {"ua": "...", "ru": "..."}}.
    """
    v = p.get(key)
    if not v:
        return None
    val = get_text(v) if isinstance(v, dict) else str(v)
    return val.strip().lower() if val and val.strip() else None


# Плейсхолдеры — domain-aware матчинг (false positives на hardware-каталогах).
#
# STRONG: однозначные маркеры. Любое substring-вхождение = placeholder.
# (Это фразы, которые НИКОГДА не встречаются в нормальном товаре.)
STRONG_PLACEHOLDERS = [
    "lorem ipsum", "lorem ip", "dolor sit amet",
    "заполнить позже", "заповнити пізніше", "опис буде пізніше",
    "тест тест", "test test test", "xxxxxx", "######",
    "описание описание", "опис опис",
]

# WEAK: короткие/неоднозначные токены. Требуют:
#   1) совпадения по ГРАНИЦЕ слова (\btoken\b) — чтобы не ловить внутри SKU
#      (напр. "tba" в коде детали 14AM00TBAS)
#   2) ДОМИНИРОВАНИЯ маркера в поле — текст должен быть коротким,
#      а не 500-символьное описание с одним "todo" где-то в середине
WEAK_PLACEHOLDERS = ["todo", "tbd", "tba", "n/a", "xxx", "заглушка-текст"]
WEAK_RE = {w: re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE) for w in WEAK_PLACEHOLDERS}

# ВАЖНО: «заглушка» / «placeholder» УДАЛЕНЫ из списков —
# в hardware-каталогах «заглушка» это реальный товар
# (socket blanking plug, торцевая заглушка для полива, заглушка горячего башмака).
# Это нарушало заявленный принцип «низкий recall, высокая точность».


def detect_placeholders(title, description, short_desc):
    """Domain-aware детект плейсхолдеров. Возвращает список найденных маркеров."""
    full = (title + " " + description + " " + short_desc)
    full_lower = full.lower()
    found = []

    # STRONG — substring match (эти фразы безопасны)
    for ph in STRONG_PLACEHOLDERS:
        if ph in full_lower:
            found.append(ph)

    # WEAK — только если маркер ДОМИНИРУЕТ в коротком тексте.
    # Эвристика: суммарная длина значимого текста < 60 символов
    # (т.е. поле фактически пустое, кроме плейсхолдера).
    stripped = full.strip()
    if len(stripped) < 60:
        for w, rx in WEAK_RE.items():
            if rx.search(full):
                found.append(w)

    return found


def analyze(products):
    findings = defaultdict(list)
    main = [p for p in products if p.get("article") == p.get("parent_article")]
    all_products = products  # для проверки модификаций

    # Группируем модификации по родительскому артикулу
    by_parent = defaultdict(list)
    for p in all_products:
        parent = p.get("parent_article")
        if parent:
            by_parent[parent].append(p)

    # ── 1-4: text-vs-characteristics для каждого главного товара ──────────
    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title"))
        description = strip_html(get_text(p.get("description")))
        short_desc = strip_html(get_text(p.get("short_description")))

        full_text = " ".join([title, description, short_desc])

        # 1. Материал
        mat_in_text = detect_in_text(full_text, MATERIALS)
        mat_in_chars = get_char_value(p, ["material", "materal", "matarial"])
        if mat_in_chars:
            mat_in_chars_set = detect_in_text(mat_in_chars, MATERIALS)
            extra_in_text = mat_in_text - mat_in_chars_set
            if extra_in_text and mat_in_chars_set and extra_in_text != mat_in_text:
                findings["material_conflict"].append({
                    "article": article, "title": title,
                    "in_text": list(mat_in_text),
                    "in_characteristics": list(mat_in_chars_set),
                    "char_value": mat_in_chars,
                })

        # 2. Страна
        country_in_text = detect_in_text(full_text, COUNTRIES)
        country_in_chars = get_char_value(p, ["country", "kranaVirobnik", "manufacturerCountry"])
        if country_in_chars:
            country_in_chars_set = detect_in_text(country_in_chars, COUNTRIES)
            if country_in_text and country_in_chars_set and not (country_in_text & country_in_chars_set):
                findings["country_conflict"].append({
                    "article": article, "title": title,
                    "in_text": list(country_in_text),
                    "in_characteristics": list(country_in_chars_set),
                    "char_value": country_in_chars,
                })

        # 3. Цвет (color — top-level поле, не в characteristics)
        color_in_title_set = detect_in_text(title, COLORS)
        color_value = get_top_level_value(p, "color") or get_char_value(p, ["color", "kolr", "colour"])
        if color_value:
            color_in_chars_set = detect_in_text(color_value, COLORS)
            if color_in_title_set and color_in_chars_set and not (color_in_title_set & color_in_chars_set):
                findings["color_conflict"].append({
                    "article": article, "title": title,
                    "in_title": list(color_in_title_set),
                    "in_characteristics": list(color_in_chars_set),
                    "char_value": color_value,
                })

        # 4. Размеры NNxNN
        size_pattern = re.compile(r"\b(\d{2,4})\s*[×x]\s*(\d{2,4})\b")
        title_sizes = set(size_pattern.findall(title))
        desc_sizes = set(size_pattern.findall(description))
        if title_sizes and desc_sizes:
            if not (title_sizes & desc_sizes):
                findings["size_conflict"].append({
                    "article": article, "title": title,
                    "in_title": list(title_sizes),
                    "in_description": list(desc_sizes)[:3],
                })

        # ── 5: discount vs price math ─────────────────────────────────────
        try:
            price = float(p.get("price") or 0)
            price_old = float(p.get("price_old") or 0)
            discount_field = p.get("discount")
            if discount_field is None:
                discount = 0
            else:
                # discount может быть {"id": N, "value": ...} или просто числом
                if isinstance(discount_field, dict):
                    discount = float(discount_field.get("value", 0) or 0)
                else:
                    discount = float(discount_field or 0)

            if price_old > price > 0 and discount > 0:
                actual_pct = (price_old - price) / price_old * 100
                if abs(actual_pct - discount) > 5:  # допуск ±5%
                    findings["discount_math_mismatch"].append({
                        "article": article, "title": title,
                        "price": price, "price_old": price_old,
                        "stated_discount": discount,
                        "actual_discount": round(actual_pct, 1),
                    })
        except (TypeError, ValueError):
            pass

        # ── 6: плейсхолдеры в текстах (domain-aware) ─────────────────────
        found_placeholders = detect_placeholders(title, description, short_desc)
        if found_placeholders:
            findings["placeholder_text"].append({
                "article": article, "title": title,
                "found": found_placeholders[:3],
            })

        # ── 7: модификации с разной материал/странной от родителя ─────────
        mods = by_parent.get(article, [])
        if len(mods) > 1:
            parent_mat = get_char_value(p, ["material", "materal", "matarial"])
            parent_country = get_char_value(p, ["country", "kranaVirobnik", "manufacturerCountry"])
            mod_mats = set()
            mod_countries = set()
            for mod in mods:
                if mod.get("article") == article:
                    continue  # сам себя не считаем
                mm = get_char_value(mod, ["material", "materal", "matarial"])
                mc = get_char_value(mod, ["country", "kranaVirobnik", "manufacturerCountry"])
                if mm:
                    mod_mats.add(mm)
                if mc:
                    mod_countries.add(mc)

            mat_drift = parent_mat and mod_mats and not all(m == parent_mat for m in mod_mats)
            country_drift = parent_country and mod_countries and not all(c == parent_country for c in mod_countries)
            if mat_drift or country_drift:
                findings["mod_attribute_drift"].append({
                    "article": article, "title": title,
                    "parent_material": parent_mat,
                    "mod_materials": list(mod_mats) if mat_drift else None,
                    "parent_country": parent_country,
                    "mod_countries": list(mod_countries) if country_drift else None,
                })

    # ── 8: negative price / negative stock (применим ко всем, не только main) ──
    for p in all_products:
        article = p.get("article", "")
        title = get_text(p.get("title"))
        try:
            price = float(p.get("price") or 0)
            if price < 0:
                findings["negative_price"].append({
                    "article": article, "title": title, "price": price,
                })
        except (TypeError, ValueError):
            pass

        # negative residues (если есть учет складов)
        residues = p.get("residues") or []
        if isinstance(residues, list):
            for r in residues:
                if isinstance(r, dict):
                    try:
                        qty = int(r.get("quantity", 0) or 0)
                        if qty < 0:
                            findings["negative_stock"].append({
                                "article": article, "title": title,
                                "warehouse": r.get("warehouse"), "quantity": qty,
                            })
                            break
                    except (TypeError, ValueError):
                        pass

    return findings, len(main)


# Список всех проверок для документации в отчёте
ALL_CHECKS = [
    ("material_conflict", "Матеріал у тексті ≠ characteristics.material"),
    ("country_conflict", "Країна у тексті ≠ characteristics.country"),
    ("color_conflict", "Колір в title ≠ полю color"),
    ("size_conflict", "Розмір в title ≠ розміру в description"),
    ("discount_math_mismatch", "Заявлена discount ≠ (price_old - price) / price_old"),
    ("placeholder_text", "Плейсхолдери в тексті (lorem ipsum, todo, тест тест...)"),
    ("mod_attribute_drift", "Модифікації одного товару мають різні material/country"),
    ("negative_price", "Ціна < 0 (баг імпорту)"),
    ("negative_stock", "Залишок на складі < 0 (баг обліку)"),
]


def generate_report(findings, total_main):
    md = []
    md.append(f"# Перевірка консистентності `{DOMAIN or 'локальний каталог'}`\n")
    md.append(f"**Головних товарів:** {total_main}\n")

    n = lambda k: len(findings.get(k, []))

    # Список того, что проверялось — чтобы пользователь видел масштаб даже при 0 конфликтов
    md.append("## 🔬 Що перевіряється\n")
    md.append("| # | Перевірка | Знайдено |")
    md.append("|---|---|---|")
    for i, (key, desc) in enumerate(ALL_CHECKS, 1):
        cnt = n(key)
        marker = "🟢" if cnt == 0 else ("🟡" if cnt < 5 else "🔴")
        md.append(f"| {i} | {desc} | {marker} {cnt} |")
    md.append("")

    total_conflicts = sum(n(k) for k, _ in ALL_CHECKS)
    if total_conflicts == 0:
        md.append(f"## ✅ Конфліктів не знайдено\n")
        md.append(f"Перевірено **{len(ALL_CHECKS)} типів конфліктів** на **{total_main} головних товарах**. Всі узгоджено.\n")
    else:
        md.append(f"## 📋 Знахідки ({total_conflicts} всього)\n")

        # Детали по каждому типу
        type_labels = {
            "material_conflict": "🧵 Конфлікт матеріалу",
            "country_conflict": "🌍 Конфлікт країни",
            "color_conflict": "🎨 Конфлікт кольору",
            "size_conflict": "📏 Конфлікт розміру",
            "discount_math_mismatch": "💸 Заявлена знижка ≠ реальній",
            "placeholder_text": "📝 Плейсхолдери в тексті",
            "mod_attribute_drift": "🔀 Дрифт атрибутів модифікацій",
            "negative_price": "💰 Від'ємна ціна",
            "negative_stock": "📦 Від'ємний залишок",
        }

        # Текстовые конфликты
        for typ in ("material_conflict", "country_conflict", "color_conflict", "size_conflict"):
            items = findings.get(typ, [])
            if not items:
                continue
            md.append(f"### {type_labels[typ]} ({len(items)})\n")
            md.append("| Артикул | Назва | У тексті | У характеристиках |")
            md.append("|---|---|---|---|")
            for it in items[:15]:
                in_text = ", ".join(it.get("in_text", it.get("in_title", []))[:2])
                in_chars = ", ".join(it.get("in_characteristics", [])[:2]) or str(it.get("char_value", "—"))[:30]
                md.append(f"| `{it['article']}` | {it['title'][:50]} | {in_text} | {in_chars} |")
            md.append("")

        # Discount math
        items = findings.get("discount_math_mismatch", [])
        if items:
            md.append(f"### {type_labels['discount_math_mismatch']} ({len(items)})\n")
            md.append("| Артикул | Назва | Ціна | Стара ціна | Заявлено discount | Реальна discount |")
            md.append("|---|---|---|---|---|---|")
            for it in items[:15]:
                md.append(f"| `{it['article']}` | {it['title'][:40]} | {it['price']} | {it['price_old']} | {it['stated_discount']}% | {it['actual_discount']}% |")
            md.append("")

        # Placeholders
        items = findings.get("placeholder_text", [])
        if items:
            md.append(f"### {type_labels['placeholder_text']} ({len(items)})\n")
            md.append("| Артикул | Назва | Знайдено |")
            md.append("|---|---|---|")
            for it in items[:15]:
                md.append(f"| `{it['article']}` | {it['title'][:50]} | {', '.join(it['found'])} |")
            md.append("")

        # Mod drift
        items = findings.get("mod_attribute_drift", [])
        if items:
            md.append(f"### {type_labels['mod_attribute_drift']} ({len(items)})\n")
            md.append("Модифікації одного товару мають різні значення material/country — або родитель і модифікації різні. "
                     "Це підозріло (зазвичай вони мають один материал).\n")
            md.append("| Артикул | У родителя | В модифікаціях |")
            md.append("|---|---|---|")
            for it in items[:10]:
                parts = []
                if it.get("mod_materials"):
                    parts.append(f"material: {it.get('parent_material', '—')} vs {it['mod_materials']}")
                if it.get("mod_countries"):
                    parts.append(f"country: {it.get('parent_country', '—')} vs {it['mod_countries']}")
                md.append(f"| `{it['article']}` | див. деталі | {' / '.join(parts)} |")
            md.append("")

        # Negatives
        items = findings.get("negative_price", [])
        if items:
            md.append(f"### {type_labels['negative_price']} ({len(items)})\n")
            md.append("| Артикул | Назва | Ціна |")
            md.append("|---|---|---|")
            for it in items[:10]:
                md.append(f"| `{it['article']}` | {it['title'][:50]} | {it['price']} |")
            md.append("")

        items = findings.get("negative_stock", [])
        if items:
            md.append(f"### {type_labels['negative_stock']} ({len(items)})\n")
            md.append("| Артикул | Назва | Склад | Залишок |")
            md.append("|---|---|---|---|")
            for it in items[:10]:
                md.append(f"| `{it['article']}` | {it['title'][:40]} | {it['warehouse']} | {it['quantity']} |")
            md.append("")

        md.append("## 💡 Що з цим робити\n")
        md.append("- Для кожного конфлікту: **руками** перевірити, що правильне — текст чи характеристики")
        md.append("- Часто проблема в тому що при копіюванні товара забули поміняти")
        md.append("- Якщо проблема системна (багато конфліктів) — перевірити CSV-імпорт або процес заведення товарів")
        if findings.get("discount_math_mismatch"):
            md.append("- Discount math: або перерахувати `discount` через `(price_old - price) / price_old * 100`, або виправити ціни")
        if findings.get("placeholder_text"):
            md.append("- Плейсхолдери: знайти й переписати реальним описом (lorem ipsum / todo / тест — це безсумнівно баг)")
        if findings.get("negative_price") or findings.get("negative_stock"):
            md.append("- Від'ємні цифри: терміново перевірити імпорт. На сайт такі товари показуватись не повинні.")

    md.append("\n---\n")
    md.append("🔍 *Згенеровано скілом [horoshop-consistency](https://github.com/IgorShutko/horoshop-claude-skill) — Target+ Agency.*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Horoshop consistency check")
    parser.add_argument("--from-file", help="Каталог из локального JSON")
    args = parser.parse_args()

    if args.from_file:
        products = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    else:
        if not all([DOMAIN, LOGIN, PASSWORD]):
            print("ERROR: env not set", file=sys.stderr)
            sys.exit(1)
        print(f"=== Consistency check {DOMAIN} ===\n[1/3] Выгрузка каталога...")
        products = export_catalog()
        Path("catalog.json").write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    print("[2/3] Анализ конфликтов...")
    findings, total_main = analyze(products)
    Path("consistency.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/3] Формирование CONSISTENCY_REPORT.md...")
    report = generate_report(findings, total_main)
    Path("CONSISTENCY_REPORT.md").write_text(report, encoding="utf-8")

    total_conflicts = sum(len(findings.get(k, [])) for k in ("material_conflict", "country_conflict", "color_conflict", "size_conflict"))
    print(f"\n━━━ TL;DR ━━━")
    print(f"  Главных товаров: {total_main}")
    print(f"  Конфликтов всего: {total_conflicts}")
    for k in ("material_conflict", "country_conflict", "color_conflict", "size_conflict"):
        c = len(findings.get(k, []))
        if c:
            print(f"    {k}: {c}")
    print(f"\nФайлы: CONSISTENCY_REPORT.md, consistency.json")


if __name__ == "__main__":
    main()

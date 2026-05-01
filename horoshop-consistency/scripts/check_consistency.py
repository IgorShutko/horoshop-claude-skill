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
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Consistency)"})

_token = None
_token_time = 0


def get_token():
    global _token, _token_time
    import time
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


def analyze(products):
    findings = defaultdict(list)
    main = [p for p in products if p.get("article") == p.get("parent_article")]

    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title"))
        description = strip_html(get_text(p.get("description")))
        short_desc = strip_html(get_text(p.get("short_description")))

        # Текст для проверки = title + description + short_description
        full_text = " ".join([title, description, short_desc])

        # 1. Материал
        mat_in_text = detect_in_text(full_text, MATERIALS)
        # Стандартные ключи characteristics для материала
        mat_in_chars = get_char_value(p, ["material", "materal", "matarial"])
        if mat_in_chars:
            mat_in_chars_set = detect_in_text(mat_in_chars, MATERIALS)
            # Если в тексте упомянуты материалы которых нет в characteristics
            extra_in_text = mat_in_text - mat_in_chars_set
            if extra_in_text and mat_in_chars_set and extra_in_text != mat_in_text:
                # Конфликт: текст и характеристики ссылаются на разные материалы
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

        # 3. Цвет
        color_in_title_set = detect_in_text(title, COLORS)
        color_in_chars = get_char_value(p, ["color", "kolr", "colour"])
        if color_in_chars:
            color_in_chars_set = detect_in_text(color_in_chars, COLORS)
            if color_in_title_set and color_in_chars_set and not (color_in_title_set & color_in_chars_set):
                findings["color_conflict"].append({
                    "article": article, "title": title,
                    "in_title": list(color_in_title_set),
                    "in_characteristics": list(color_in_chars_set),
                    "char_value": color_in_chars,
                })

        # 4. Размеры (грубо: ловим NNxNN или NN×NN в title и описании, сравниваем)
        size_pattern = re.compile(r"\b(\d{2,4})\s*[×x]\s*(\d{2,4})\b")
        title_sizes = set(size_pattern.findall(title))
        desc_sizes = set(size_pattern.findall(description))
        if title_sizes and desc_sizes:
            # Если в title и description полностью разные размеры — конфликт
            if not (title_sizes & desc_sizes):
                findings["size_conflict"].append({
                    "article": article, "title": title,
                    "in_title": list(title_sizes),
                    "in_description": list(desc_sizes)[:3],
                })

    return findings, len(main)


def generate_report(findings, total_main):
    md = []
    md.append(f"# Перевірка консистентності `{DOMAIN or 'локальний каталог'}`\n")
    md.append(f"**Головних товарів:** {total_main}\n")

    n = lambda k: len(findings.get(k, []))

    if not any(findings.get(k) for k in ("material_conflict", "country_conflict", "color_conflict", "size_conflict")):
        md.append("Конфліктів не знайдено. ✅\n")
    else:
        md.append("## 📋 Знахідки\n")
        md.append("| Тип конфлікту | Кількість |")
        md.append("|---|---|")
        if n("material_conflict"): md.append(f"| Матеріал у тексті ≠ характеристикам | {n('material_conflict')} |")
        if n("country_conflict"): md.append(f"| Країна у тексті ≠ характеристикам | {n('country_conflict')} |")
        if n("color_conflict"): md.append(f"| Колір в title ≠ характеристикам | {n('color_conflict')} |")
        if n("size_conflict"): md.append(f"| Розмір в title ≠ опису | {n('size_conflict')} |")
        md.append("")

        for typ, label in (
            ("material_conflict", "🧵 Конфлікт матеріалу"),
            ("country_conflict", "🌍 Конфлікт країни"),
            ("color_conflict", "🎨 Конфлікт кольору"),
            ("size_conflict", "📏 Конфлікт розміру"),
        ):
            items = findings.get(typ, [])
            if not items:
                continue
            md.append(f"## {label}\n")
            md.append("| Артикул | Назва | У тексті | У характеристиках |")
            md.append("|---|---|---|---|")
            for it in items[:15]:
                in_text = ", ".join(it.get("in_text", it.get("in_title", []))[:2])
                in_chars = ", ".join(it.get("in_characteristics", [])[:2]) or it.get("char_value", "—")[:30]
                md.append(f"| `{it['article']}` | {it['title'][:50]} | {in_text} | {in_chars} |")
            md.append("")

        md.append("## 💡 Що з цим робити\n")
        md.append("- Для кожного конфлікту: **руками** перевірити, що правильне — текст чи характеристики")
        md.append("- Часто проблема в тому що при копіюванні товара забули поміняти")
        md.append("- Якщо проблема системна (багато конфліктів) — перевірити CSV-імпорт або процес заведення товарів")

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

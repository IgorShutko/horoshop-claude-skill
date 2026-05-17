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


# ─── Паттерны (адаптация stop-slop фреймворка Hardik Pandya для UA/RU) ─────

# 1. Throat-clearers — заглушки перед мыслью
THROAT_CLEARERS = [
    # RU
    "стоит отметить", "следует отметить", "следует заметить",
    "стоит обратить внимание", "необходимо отметить",
    "хотелось бы сказать", "хотелось бы", "надо сказать",
    "по сути", "на самом деле",
    # UA
    "варто зазначити", "варто звернути увагу",
    "слід відмітити", "слід зауважити", "слід зазначити",
    "хотілось би сказати", "хотілось би", "треба сказати",
    "по суті", "насправді ж",
]

# 2. Эмфазные пустышки (emphasis crutches) + длинные глагольные обороты
AI_SLOP_PHRASES = [
    # RU
    "является", "представляет собой", "выступает в качестве",
    "при этом", "в целом", "в общем",
    "буквально", "крайне", "весьма", "очень-очень",
    "действительно", "по-настоящему",
    "безусловно", "однозначно", "непременно",
    "не просто",
    # UA
    "являє собою", "виступає в якості", "виступає як",
    "при цьому", "загалом", "в цілому",
    "буквально", "вкрай", "вельми",
    "справді", "дійсно",
    "однозначно", "безумовно", "неодмінно",
]

# 3. Маркетинг-вода — превосходные степени без основания + псевдо-эмо
MARKETING_FLUFF = [
    # RU
    "высочайшее качество", "непревзойденный", "уникальный",
    "инновационный", "передовой", "лидер рынка",
    "безупречный", "исключительный", "революционный",
    "специально для вас", "именно для вашего комфорта",
    "ваш надёжный помощник", "ваш надежный помощник", "ваш лучший выбор",
    # UA
    "найвища якість", "неперевершений", "унікальний",
    "інноваційний", "передовий", "лідер ринку",
    "бездоганний", "винятковий", "революційний",
    "спеціально для вас", "саме для вашого комфорту",
    "ваш надійний помічник", "ваш найкращий вибір",
]

# 4. Бизнес-жаргон
BUSINESS_JARGON = [
    # RU/EN borrowed
    "реализовать", "внедрить", "оптимизировать", "масштабировать",
    "синергия", "экосистема", "парадигма",
    "в современных реалиях",
    # UA
    "реалізувати", "впровадити", "оптимізувати", "масштабувати",
    "синергія", "екосистема", "парадигма",
    "у нашій парадигмі", "з огляду на сучасні реалії",
]

# 5. Vague declaratives — что-то важное без указания что
VAGUE_DECLARATIVES = [
    # RU
    "причины структурные", "последствия значительны",
    "это имеет значение", "ставки высоки",
    # UA
    "причини є структурними", "наслідки значні",
    "це має значення", "ставки високі",
]

# 6. Lazy extremes — ленивые крайности
LAZY_EXTREMES = [
    # RU
    "всегда", "никогда", "каждый раз", "ни один",
    # UA
    "завжди", "ніколи", "кожного разу", "жоден",
]

# 7. Бинарные контрасты — «не X, а Y»
BINARY_CONTRAST_RE = re.compile(
    r"\bне\s+(?:просто\s+)?\w+[,.\s—–-]+(?:а|але|но|это|це)\b",
    re.IGNORECASE,
)

# 8. False agency — неодушевлённое + человеческий глагол
FALSE_AGENCY_PATTERNS = [
    # RU
    r"\b(?:товар|куртка|матрас|комплект|тканина|технологія|дизайн)\s+(?:дозволяє|пропонує|забезпечує|розповідає|знає|пам.ятає)\b",
    r"\b(?:товар|куртка|матрас|комплект|ткань|технология|дизайн)\s+(?:позволяет|предлагает|обеспечивает|рассказывает|знает|помнит)\b",
]
FALSE_AGENCY_RE = [re.compile(p, re.IGNORECASE) for p in FALSE_AGENCY_PATTERNS]

# 9. Em dashes (без пробелов — английский стиль)
EM_DASH_RE = re.compile(r"\w—\w")

# 10. Дубли слов
DUP_WORDS_RE = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)

# 11. Caps lock — слово из 6+ заглавных. Цифры внутри = SKU-подобное, скипаем отдельно.
CAPS_LOCK_RE = re.compile(r"\b[А-ЯЁІЇЄҐA-Z][А-ЯЁІЇЄҐA-Z0-9-]{5,}\b")

# 12. Дубли БУКВ (не цифр!): «оооочень» — баг. «30000 мАг» — спека, НЕ баг.
#     Раньше \w ловил цифры → false positive на спеках hardware.
LETTER_DUP_RE = re.compile(r"([A-Za-zА-Яа-яЁёІіЇїЄєҐґ])\1{3,}", re.IGNORECASE)

# 13. HTML-entities в тексте — необработанные ампам-сущности
HTML_ENTITY_RE = re.compile(r"&(?:nbsp|amp|quot|lt|gt|sup\d|times|sub\d|copy|trade|reg|deg|euro|pound|hellip|ldquo|rdquo|lsquo|rsquo|mdash|ndash|laquo|raquo|[a-z]{2,8}|#\d+);", re.IGNORECASE)

# 14. Стена текста — длинное описание без структурных тегов
NO_STRUCTURE_THRESHOLD = 500  # символов без HTML-разметки
STRUCTURE_TAGS_RE = re.compile(r"<(p|br|h[1-6]|ul|ol|li|table|tr|td|div)\b", re.IGNORECASE)


def split_sentences(text):
    """Грубое разделение на предложения."""
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"[.!?]+\s+", text) if s.strip()]


def _find_phrases(plain, phrases, limit=3):
    """Ищет вхождения по подстроке. Возвращает уникальный список."""
    found = []
    seen = set()
    for ph in phrases:
        if ph.lower() in plain and ph.lower() not in seen:
            found.append(ph)
            seen.add(ph.lower())
            if len(found) >= limit:
                break
    return found


def check_text(text, field_type="text", brand_title_tokens=None):
    """Возвращает список проблем для одного текста.

    field_type: 'description' / 'short_description' / 'marketplace_description' /
                'title' / 'seo_title' / 'seo_description' / 'h1_title' / 'text'
    brand_title_tokens: set ALL-CAPS токенов из brand+title товара —
                        вайтлист для caps_lock (бренды типа INKBIRD не «крик»).
    """
    issues = []
    if not text:
        return issues
    brand_title_tokens = brand_title_tokens or set()
    raw = text  # с HTML
    plain = strip_html(text).lower()
    plain_orig = strip_html(text)

    # 0. HTML-entities в RAW тексте (не должны попадать в продакшен)
    entities = HTML_ENTITY_RE.findall(raw)
    # Также проверяем в plain_orig — после strip_html сущности тоже могут оставаться
    entities_in_plain = HTML_ENTITY_RE.findall(plain_orig)
    all_entities = entities + entities_in_plain
    if all_entities:
        # Уникальные, до 5
        seen = set()
        unique = []
        for e in all_entities:
            if e.lower() not in seen:
                seen.add(e.lower())
                unique.append(e)
                if len(unique) >= 5:
                    break
        issues.append({"type": "html_entities_in_text", "examples": unique, "count": len(all_entities)})

    # 0b. Стена текста (только для description) — длинный raw без структурных тегов
    if field_type == "description" and len(plain_orig) > NO_STRUCTURE_THRESHOLD:
        if not STRUCTURE_TAGS_RE.search(raw):
            issues.append({
                "type": "no_paragraphs",
                "char_count": len(plain_orig),
                "note": "опис >500 символів без <p>/<br>/<ul>/<table>",
            })

    # 1. Throat-clearers (заглушки)
    if found := _find_phrases(plain, THROAT_CLEARERS):
        issues.append({"type": "throat_clearer", "examples": found})

    # 2. AI-стоп-слоп / эмфазные пустышки
    if found := _find_phrases(plain, AI_SLOP_PHRASES):
        issues.append({"type": "ai_slop", "examples": found})

    # 3. Маркетинг-вода
    if found := _find_phrases(plain, MARKETING_FLUFF):
        issues.append({"type": "marketing_fluff", "examples": found})

    # 4. Бизнес-жаргон
    if found := _find_phrases(plain, BUSINESS_JARGON):
        issues.append({"type": "business_jargon", "examples": found})

    # 5. Vague declaratives
    if found := _find_phrases(plain, VAGUE_DECLARATIVES):
        issues.append({"type": "vague_declarative", "examples": found})

    # 6. Lazy extremes (только если без числового пруфа рядом)
    extremes_found = _find_phrases(plain, LAZY_EXTREMES, limit=5)
    if extremes_found:
        issues.append({"type": "lazy_extreme", "examples": extremes_found[:3]})

    # 7. Бинарные контрасты «не X, а Y»
    binary_matches = BINARY_CONTRAST_RE.findall(plain_orig)
    if binary_matches:
        issues.append({"type": "binary_contrast", "count": len(binary_matches), "example": binary_matches[0]})

    # 8. False agency (неодушевлённое + чел. глагол)
    for rx in FALSE_AGENCY_RE:
        m = rx.search(plain_orig)
        if m:
            issues.append({"type": "false_agency", "example": m.group(0)})
            break

    # 9. Em dashes без пробелов
    em_dashes = EM_DASH_RE.findall(plain_orig)
    if em_dashes:
        issues.append({"type": "em_dash", "count": len(em_dashes)})

    # 10. Дубли слов
    dups = DUP_WORDS_RE.findall(plain_orig)
    dups = [d for d in dups if d.lower() not in ("так", "ну")]
    if dups:
        issues.append({"type": "duplicate_words", "examples": list(set(dups))[:3]})

    # 11. CAPS LOCK слова — фильтруем бренды/модели/SKU (шум на hardware-каталогах)
    KNOWN_ABBR = {"GTIN", "USB", "USA", "GMBH", "LED", "USR", "GPS", "RGB", "PWM",
                  "API", "HDMI", "VGA", "USBC", "OLED", "LCD", "TFT", "ABS", "PLA",
                  "MOSFET", "CNC", "OBD", "ESP", "GSM", "NFC", "RFID", "PCB"}
    caps_raw = CAPS_LOCK_RE.findall(plain_orig)
    caps = []
    for c in caps_raw:
        if len(c) <= 6:
            continue
        cu = c.upper()
        if cu in KNOWN_ABBR:
            continue
        # SKU-подобное: содержит цифру или дефис → это модель/артикул, не «крик»
        if any(ch.isdigit() for ch in c) or "-" in c:
            continue
        # Бренд/модель из title/brand товара → не «крик прозы»
        if cu in brand_title_tokens:
            continue
        caps.append(c)
    if caps:
        issues.append({"type": "caps_lock", "examples": list(set(caps))[:3]})

    # 12. Дубли букв
    letter_dups = LETTER_DUP_RE.findall(plain_orig)
    if letter_dups:
        issues.append({"type": "letter_repeats", "examples": list(set(letter_dups))[:3]})

    # 13. Длинные предложения
    sentences = split_sentences(plain_orig)
    long_sentences = [s for s in sentences if len(s.split()) > 35]
    if long_sentences:
        issues.append({
            "type": "long_sentence",
            "count": len(long_sentences),
            "example": long_sentences[0][:200] + "...",
        })

    return issues


def detect_template_phrases(products, lang, min_occurrences=5, min_phrase_len=30):
    """Ищет фразы (>=30 символов), повторяющиеся у >=N товаров.

    Это находит copy-paste шаблоны — одинаковые куски текста в карточках.
    Возвращает список (phrase, count, example_articles).
    """
    from collections import Counter

    main = [p for p in products if p.get("article") == p.get("parent_article")]
    phrase_to_articles = defaultdict(list)

    for p in main:
        article = p.get("article", "")
        for field in ("description", "short_description", "marketplace_description"):
            text = strip_html(get_text(p.get(field), lang))
            if not text or len(text) < min_phrase_len:
                continue
            # Разбиваем по предложениям (грубо)
            for sent in re.split(r"[.!?\n]+", text):
                sent = sent.strip()
                if len(sent) >= min_phrase_len and len(sent) <= 200:
                    phrase_to_articles[sent].append(article)

    templates = []
    for phrase, articles in phrase_to_articles.items():
        # Уникальные товары (один товар может иметь фразу в нескольких полях)
        unique_articles = list(set(articles))
        if len(unique_articles) >= min_occurrences:
            templates.append({
                "phrase": phrase[:100] + ("..." if len(phrase) > 100 else ""),
                "occurrences": len(unique_articles),
                "articles_sample": unique_articles[:5],
            })

    # Сортируем: чем больше дублей, тем выше
    templates.sort(key=lambda x: -x["occurrences"])
    return templates[:10]  # топ-10


def analyze(products, lang):
    findings = defaultdict(list)
    main = [p for p in products if p.get("article") == p.get("parent_article")]

    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title"), lang)

        # ALL-CAPS токены из title + brand товара → вайтлист для caps_lock.
        # На hardware-каталогах бренды (INKBIRD, BIGTREETECH) — это не «крик».
        brand_val = p.get("brand")
        if isinstance(brand_val, dict):
            brand_str = get_text(brand_val, lang) or str(brand_val.get("value", ""))
        else:
            brand_str = str(brand_val or "")
        brand_title_tokens = set()
        for tok in re.findall(r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ0-9-]{3,}", f"{title} {brand_str}"):
            if tok.isupper() or any(ch.isdigit() for ch in tok):
                brand_title_tokens.add(tok.upper())

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
            field_issues = check_text(text, field_type=field_name, brand_title_tokens=brand_title_tokens)
            for issue in field_issues:
                issue["field"] = field_name
                product_issues.append(issue)

        if product_issues:
            findings["products_with_issues"].append({
                "article": article,
                "title": title,
                "issues": product_issues,
            })

    # Cross-product: template phrases (одна фраза у >=5 товаров)
    templates = detect_template_phrases(products, lang)
    if templates:
        findings["template_phrases"] = templates

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

    # Шаблонні фрази (cross-product): одна фраза у багатьох товарах
    templates = findings.get("template_phrases", [])
    if templates:
        md.append(f"## 🔁 Шаблонні фрази (copy-paste у {len(templates)} групах)\n")
        md.append("Одна й та сама фраза в описах різних товарів — задушує унікальність контенту.\n")
        md.append("| Фраза | Товарів | Приклади артикулів |")
        md.append("|---|---|---|")
        for t in templates:
            phrase = t["phrase"].replace("|", "\\|")
            arts = ", ".join(f"`{a}`" for a in t["articles_sample"])
            md.append(f"| {phrase} | {t['occurrences']} | {arts} |")
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
                elif t == "html_entities_in_text":
                    examples = fmt_examples(iss.get("examples", []))
                    md.append(f"- 🔴 `{f}` — **HTML-entities в тексті** ({iss.get('count', 0)} шт): {examples}")
                elif t == "no_paragraphs":
                    md.append(f"- ⚠️ `{f}` — **стіна тексту** ({iss.get('char_count', 0)} симв без `<p>`/`<br>`/`<ul>`)")
                else:
                    examples = fmt_examples(iss.get("examples", []))
                    md.append(f"- ⚠️ `{f}` — **{t}**: {examples}")
            md.append("")

    # ── stop-slop scoring (1-10 по 5 измерениям) ──────────────────────────
    md.append("\n## 🎯 Stop-Slop Score\n")
    md.append("За фреймворком [stop-slop](https://github.com/hvpandya/stop-slop) (Hardik Pandya). 1-10, де 10 = ідеально.\n")

    issues_per_product = (sum(len(p["issues"]) for p in products) / max(len(products), 1)) if products else 0
    affected_pct = len(products) / total_main * 100 if total_main else 0

    # Эвристика: чем больше типов проблем + чем больше товаров затронуто, тем хуже
    directness = max(1, 10 - by_type.get("throat_clearer", 0) // max(total_main // 10, 1) - by_type.get("ai_slop", 0) // max(total_main // 10, 1))
    rhythm = max(1, 10 - by_type.get("long_sentence", 0) // max(total_main // 10, 1) - by_type.get("em_dash", 0) // max(total_main // 5, 1))
    trust = max(1, 10 - by_type.get("marketing_fluff", 0) // max(total_main // 10, 1) - by_type.get("vague_declarative", 0) // max(total_main // 5, 1))
    authenticity = max(1, 10 - by_type.get("false_agency", 0) // max(total_main // 10, 1) - by_type.get("binary_contrast", 0) // max(total_main // 5, 1))
    density = max(1, 10 - by_type.get("business_jargon", 0) // max(total_main // 10, 1) - by_type.get("lazy_extreme", 0) // max(total_main // 10, 1))

    total = directness + rhythm + trust + authenticity + density
    md.append("| Вимір | Питання | Бал |")
    md.append("|---|---|---|")
    md.append(f"| Прямота | Твердження або оголошення? | **{directness}/10** |")
    md.append(f"| Ритм | Різноманітний чи метроном? | **{rhythm}/10** |")
    md.append(f"| Довіра | Поважає інтелект читача? | **{trust}/10** |")
    md.append(f"| Аутентичність | Звучить як людина? | **{authenticity}/10** |")
    md.append(f"| Щільність | Чи є що вирізати? | **{density}/10** |")
    md.append(f"\n**Загалом: {total}/50**")

    # Вердикт учитывает ТРИ фактора:
    # 1) total score
    # 2) affected_pct (% товаров с проблемами)
    # 3) min(dimensions) — если хоть одно измерение в красной зоне (≤3), это всегда проседание
    min_dim = min(directness, rhythm, trust, authenticity, density)
    if affected_pct >= 80 or min_dim <= 3 or total < 35:
        md.append(
            f"\n🔴 **Критично:** {affected_pct:.0f}% товарів мають проблеми, "
            f"мінімальний вимір — {min_dim}/10. Описи потребують переписування."
        )
    elif affected_pct >= 50 or min_dim <= 5 or total < 42:
        md.append(
            f"\n🟡 **Робота над помилками:** {affected_pct:.0f}% товарів зачеплено, "
            f"мінімальний вимір — {min_dim}/10. Описи стерпні, але є куди ростити."
        )
    else:
        md.append(
            f"\n🟢 **Високий рівень:** {affected_pct:.0f}% з проблемами, "
            f"мінімальний вимір — {min_dim}/10. Підтримуй стандарт."
        )
    md.append("")

    md.append("\n## 💡 Що з цим робити\n")
    if by_type.get("html_entities_in_text", 0) > 0:
        md.append(f"- 🔴 **{by_type['html_entities_in_text']} текстів з HTML-entities** (`&nbsp;`, `&sup2;`, `&times;`) — це наслідок неправильної обробки HTML при імпорті. Прогнати через декодер: `html.unescape(text)` або заповнити карточки заново.")
    if by_type.get("no_paragraphs", 0) > 0:
        md.append(f"- ⚠️ **{by_type['no_paragraphs']} стін тексту** (description >500 симв без `<p>`/`<br>`/`<ul>`) — додати структурні теги. Краще читати, краще конвертить.")
    if templates:
        md.append(f"- 🔁 **{len(templates)} шаблонних фраз** повторюються в багатьох товарах — переписати унікально для кожної категорії або групи.")
    if by_type.get("throat_clearer", 0) > 0:
        md.append(f"- **{by_type['throat_clearer']} текстів зі словами-паразитами** («варто зазначити», «слід відмітити») — почати з суті")
    if by_type.get("ai_slop", 0) > 0:
        md.append(f"- **{by_type['ai_slop']} текстів з AI-стоп-слопом** — переписати без «являє собою», «при цьому», «справді»")
    if by_type.get("marketing_fluff", 0) > 0:
        md.append(f"- **{by_type['marketing_fluff']} текстів з маркетинг-водою** — замінити «найвища якість» на конкретні факти")
    if by_type.get("business_jargon", 0) > 0:
        md.append(f"- **{by_type['business_jargon']} текстів з бізнес-жаргоном** — «реалізувати» → «зробити», «оптимізувати» → «покращити»")
    if by_type.get("binary_contrast", 0) > 0:
        md.append(f"- **{by_type['binary_contrast']} бінарних контрастів** («не X, а Y») — сказати Y напряму без негації")
    if by_type.get("false_agency", 0) > 0:
        md.append(f"- **{by_type['false_agency']} текстів з фальшивою агентністю** («тканина дозволяє вам») — назвати людину: «Ви відчуваєте комфорт завдяки тканині»")
    if by_type.get("em_dash", 0) > 0:
        md.append(f"- **{by_type['em_dash']} em-dash без пробілів** — англійський стиль, замінити на «, » або « — »")
    if by_type.get("vague_declarative", 0) > 0:
        md.append(f"- **{by_type['vague_declarative']} нечітких декларативів** — назвати конкретно або видалити")
    if by_type.get("lazy_extreme", 0) > 0:
        md.append(f"- **{by_type['lazy_extreme']} ледачих крайнощів** («завжди», «ніколи») — підкріпити цифрами або прибрати")
    if by_type.get("duplicate_words", 0) > 0:
        md.append(f"- **{by_type['duplicate_words']} текстів з повторами слів** — баг вводу, прибрати руками")
    if by_type.get("long_sentence", 0) > 0:
        md.append(f"- **{by_type['long_sentence']} довгих речень** — розбити на 2-3 коротших")
    if by_type.get("caps_lock", 0) > 0:
        md.append(f"- **{by_type['caps_lock']} CAPS-слів** — текст «кричить», замінити на нормальний регістр")

    md.append("\n---\n")
    md.append("📝 *Згенеровано скілом [horoshop-text-quality](https://github.com/IgorShutko/horoshop-claude-skill) — Target+ Agency.*  ")
    md.append("*Stop-Slop фреймворк — [Hardik Pandya](https://hvpandya.com), MIT.*  ")
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

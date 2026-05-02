#!/usr/bin/env python3
"""Аудит фотографий товаров в Horoshop.

Использование:
  python3 photo_audit.py [--from-file catalog.json] [--min-photos 4]
                        [--max-size-kb 500] [--check-sizes]

Конфиг env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD
"""

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

BASE_URL = f"https://{DOMAIN}/api" if DOMAIN else None
EXPORT_BATCH = 100
HTTP_TIMEOUT = 30

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Photo Audit)"})

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
        raise RuntimeError(f"Auth: {d}")
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
        print(f"  каталог: {len(products)}...", end="\r", flush=True)
        if len(batch) < EXPORT_BATCH:
            break
        offset += EXPORT_BATCH
    print(f"  каталог: {len(products)} товарів     ")
    return products


def get_text(field, lang=LANG):
    if not field:
        return ""
    if isinstance(field, dict):
        if "value" in field and isinstance(field["value"], dict):
            return field["value"].get(lang) or field["value"].get("ru") or ""
        return field.get(lang) or field.get("ru") or ""
    return str(field)


def head_request(url):
    """HEAD-запрос на картинку. Возвращает (status, content_length)."""
    try:
        r = session.head(url, timeout=15, allow_redirects=True)
        size = r.headers.get("Content-Length")
        return r.status_code, int(size) if size else None
    except Exception:
        return 0, None


def analyze(products, min_photos=4, max_size_kb=500, check_sizes=False):
    main = [p for p in products if p.get("article") == p.get("parent_article")]
    findings = defaultdict(list)
    main_image_to_articles = defaultdict(list)
    photo_counts = Counter()

    for p in main:
        article = p.get("article", "")
        title = get_text(p.get("title"))

        imgs = p.get("images") or []
        gallery = p.get("gallery_common") or []
        gallery_360 = p.get("gallery_360") or []

        # Хорошоп возвращает images как массив URL-строк
        all_photos = []
        for src in (imgs, gallery):
            if isinstance(src, list):
                all_photos.extend([u for u in src if isinstance(u, str)])

        photo_count = len(all_photos)
        photo_counts[photo_count] += 1

        if photo_count == 0:
            findings["no_photos"].append({"article": article, "title": title})
        elif photo_count == 1:
            findings["only_one_photo"].append({"article": article, "title": title})
        elif photo_count < min_photos:
            findings["below_min_photos"].append({
                "article": article, "title": title, "count": photo_count,
            })

        # Дубль главного фото между товарами
        if all_photos:
            main_img = all_photos[0]
            main_image_to_articles[main_img].append({"article": article, "title": title})

        # 360-обзор
        if gallery_360:
            findings["has_360"].append({"article": article, "title": title})

    # Дубликаты главных фото
    for img, items in main_image_to_articles.items():
        if len(items) > 1:
            findings["main_image_duplicates"].append({
                "image": img,
                "articles": items,
                "count": len(items),
            })

    # Размеры файлов (опционально, медленно)
    if check_sizes:
        urls_to_check = []
        for p in main:
            imgs = p.get("images") or []
            if imgs and isinstance(imgs[0], str):
                urls_to_check.append((p.get("article", ""), get_text(p.get("title")), imgs[0]))

        print(f"  HEAD-запросы на {len(urls_to_check)} главных фото...")

        def _head_with_meta(item):
            art, title, url = item
            status, size = head_request(url)
            return (art, title, url, status, size)

        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(_head_with_meta, urls_to_check))

        for art, title, url, status, size in results:
            if status != 200:
                findings["bad_image_status"].append({
                    "article": art, "title": title, "url": url, "status": status,
                })
            elif size and size > max_size_kb * 1024:
                findings["heavy_image"].append({
                    "article": art, "title": title, "url": url,
                    "size_kb": size // 1024,
                })

    return findings, photo_counts, len(main)


def fmt_count_dist(counter, total):
    """Распределение количества фото."""
    rows = []
    for count, n in sorted(counter.items()):
        pct = n / total * 100 if total else 0
        rows.append((count, n, pct))
    return rows


def generate_report(findings, photo_counts, total_main, args):
    md = []
    md.append(f"# Аудит фото товарів `{DOMAIN or 'локальний каталог'}`\n")
    md.append(f"**Головних товарів:** {total_main}")
    md.append(f"**Стандарт:** ≥{args.min_photos} фото на товар, ≤{args.max_size_kb} КБ на файл\n")

    md.append("## 📊 Розподіл за кількістю фото\n")
    md.append("| Фото на товар | Товарів | % |")
    md.append("|---|---|---|")
    for count, n, pct in fmt_count_dist(photo_counts, total_main):
        marker = "🔴" if count == 0 else ("🟡" if count < args.min_photos else "🟢")
        md.append(f"| {marker} {count} | {n} | {pct:.1f}% |")
    md.append("")

    n = lambda k: len(findings.get(k, []))

    md.append("## 🚨 Знахідки\n")
    md.append("| Проблема | Кількість | Серйозність |")
    md.append("|---|---|---|")
    if n("no_photos"):
        md.append(f"| Без фото взагалі | {n('no_photos')} | 🔴 Критично |")
    if n("only_one_photo"):
        md.append(f"| Тільки 1 фото | {n('only_one_photo')} | 🔴 Висока |")
    if n("below_min_photos"):
        md.append(f"| Менше {args.min_photos} фото | {n('below_min_photos')} | 🟡 Середня |")
    if n("main_image_duplicates"):
        md.append(f"| Дублі головних фото між товарами | {n('main_image_duplicates')} груп | 🟡 Середня |")
    if n("heavy_image"):
        md.append(f"| Тяжкі фото (>{args.max_size_kb} КБ) | {n('heavy_image')} | 🟡 LCP/CWV |")
    if n("bad_image_status"):
        md.append(f"| Биті URL фото | {n('bad_image_status')} | 🔴 |")
    if n("has_360"):
        md.append(f"| ✅ Товарів з 360-оглядом | {n('has_360')} | — |")
    md.append("")

    if findings.get("no_photos"):
        md.append("## 🔴 Без фото взагалі\n")
        md.append("| Артикул | Назва |")
        md.append("|---|---|")
        for it in findings["no_photos"][:20]:
            md.append(f"| `{it['article']}` | {it['title']} |")
        md.append("")

    if findings.get("only_one_photo"):
        md.append(f"## 🔴 Тільки 1 фото ({n('only_one_photo')})\n")
        md.append("| Артикул | Назва |")
        md.append("|---|---|")
        for it in findings["only_one_photo"][:20]:
            md.append(f"| `{it['article']}` | {it['title']} |")
        md.append(f"\n> **Чому важливо:** товари з одним фото конвертують у 2-3× гірше. Стандарт e-commerce — 4-7 фото з різних ракурсів + контекст використання.\n")

    if findings.get("main_image_duplicates"):
        md.append(f"## 🟡 Дублі головних фото між товарами ({n('main_image_duplicates')})\n")
        md.append("Часто це баг імпорту — кілька товарів отримали одну й ту саму першу картинку.\n")
        md.append("| Картинка | Кількість товарів | Артикули |")
        md.append("|---|---|---|")
        for d in findings["main_image_duplicates"][:10]:
            arts = ", ".join(f"`{a['article']}`" for a in d["articles"][:5])
            if d["count"] > 5:
                arts += f" (+{d['count']-5})"
            md.append(f"| `{d['image'][-50:]}` | {d['count']} | {arts} |")
        md.append("")

    if findings.get("heavy_image"):
        md.append(f"## 🟡 Тяжкі картинки (>{args.max_size_kb} КБ) — {n('heavy_image')}\n")
        md.append("Впливає на LCP / Core Web Vitals → нижче в Google.\n")
        md.append("| Артикул | Розмір | URL |")
        md.append("|---|---|---|")
        for it in sorted(findings["heavy_image"], key=lambda x: -x["size_kb"])[:15]:
            md.append(f"| `{it['article']}` | {it['size_kb']} КБ | {it['url'][-60:]} |")
        md.append("")

    md.append("## 💡 Рекомендації\n")
    recs = []
    if n("no_photos") > 0:
        recs.append(f"- 🔴 **Доснять {n('no_photos')} товарів без фото** — без головного фото товар невидимий в листингу.")
    if n("only_one_photo") > 0:
        recs.append(f"- 📸 **Доснять {n('only_one_photo')} товарів з 1 фото** — конверсія в 2-3× нижче. Стандарт: 4-7 фото з ракурсів + контекст використання + деталь.")
    if n("below_min_photos") > 0:
        recs.append(f"- 📸 **Дозняти {n('below_min_photos')} товарів** — менше {args.min_photos} фото. Стандарт e-commerce: 4-7 фото.")
    if n("main_image_duplicates") > 0:
        recs.append(f"- 🔄 **Замінити {n('main_image_duplicates')} груп дублікатів головних фото** — кожен товар має свою першу картинку. Часто це баг імпорту з CSV.")
    if n("heavy_image") > 0:
        recs.append(f"- 🗜 **Стиснути {n('heavy_image')} картинок** до <{args.max_size_kb} КБ (через TinyPNG, Squoosh або Photoshop «Save for Web»). Впливає на LCP / Core Web Vitals.")
    if n("bad_image_status") > 0:
        recs.append(f"- 🔴 **Перевірити {n('bad_image_status')} битих URL фото** — товар не відображається на сайті.")

    if not args.check_sizes:
        recs.append(f"- ℹ️ Перевірка ваги фото вимкнена (default). Запусти з `--check-sizes` для повного аудиту (HEAD-запит на кожне головне фото).")

    if recs:
        md.extend(recs)
    else:
        md.append("Каталог фото в порядку. ✅ Усі товари мають достатньо фото, дублів і битих URL не знайдено.")

    md.append("\n---\n")
    md.append("📸 *Згенеровано скілом [horoshop-photo-audit](https://github.com/IgorShutko/horoshop-claude-skill) — Target+ Agency.*  ")
    md.append("*Допомога з дозйомкою / обробкою фото? [TG @shutko_ads](https://t.me/shutko_ads).*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Horoshop photo audit")
    parser.add_argument("--from-file", help="Читать каталог из локального JSON")
    parser.add_argument("--min-photos", type=int, default=4)
    parser.add_argument("--max-size-kb", type=int, default=500)
    parser.add_argument("--check-sizes", action="store_true", help="HEAD-запросы на главные фото (медленно)")
    args = parser.parse_args()

    if args.from_file:
        products = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
    else:
        if not all([DOMAIN, LOGIN, PASSWORD]):
            print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы", file=sys.stderr)
            sys.exit(1)
        print(f"=== Photo audit {DOMAIN} ===\n[1/3] Выгрузка каталога...")
        products = export_catalog()
        Path("catalog.json").write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    print(f"[2/3] Анализ фото (min={args.min_photos}, max_size={args.max_size_kb}KB, check_sizes={args.check_sizes})...")
    findings, photo_counts, total_main = analyze(products, args.min_photos, args.max_size_kb, args.check_sizes)
    Path("photo_audit.json").write_text(json.dumps({
        "findings": dict(findings),
        "photo_count_distribution": dict(photo_counts),
        "total_main": total_main,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/3] Формирование PHOTO_REPORT.md...")
    report = generate_report(findings, photo_counts, total_main, args)
    Path("PHOTO_REPORT.md").write_text(report, encoding="utf-8")

    print(f"\n━━━ TL;DR ━━━")
    print(f"  Главных товаров: {total_main}")
    for k in ("no_photos", "only_one_photo", "below_min_photos", "main_image_duplicates", "heavy_image"):
        if findings.get(k):
            print(f"  {k}: {len(findings[k])}")
    print(f"\nФайлы: PHOTO_REPORT.md, photo_audit.json")


if __name__ == "__main__":
    main()

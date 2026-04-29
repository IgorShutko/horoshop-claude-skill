#!/usr/bin/env python3
"""Horoshop full audit — orchestrator.

Запускает 4 фазы аудита и формирует REPORT.md.

Конфигурация — через переменные окружения:
  HOROSHOP_DOMAIN  — домен (например `mystore.com.ua`)
  HOROSHOP_LOGIN   — API логин
  HOROSHOP_PASSWORD — API пароль
  HOROSHOP_LANG    — основной язык (по умолчанию `ua`)

Артефакты пишутся в текущую директорию:
  catalog.json         — выгрузка каталога
  categories.json      — категории
  html_audit.json      — парсинг публичных страниц
  findings.json        — все находки агрегированно
  REPORT.md            — финальный markdown-отчёт
"""

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─── Конфиг ──────────────────────────────────────────────────────────────

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")
LANG = os.getenv("HOROSHOP_LANG", "ua")

if not all([DOMAIN, LOGIN, PASSWORD]):
    print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы", file=sys.stderr)
    sys.exit(1)

BASE_URL = f"https://{DOMAIN}/api"
EXPORT_BATCH = 100
HTTP_TIMEOUT = 60
OUT = Path(".").resolve()

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop SEO Audit)"})

_token = None
_token_time = 0


def get_token():
    global _token, _token_time
    if _token and (time.time() - _token_time) < 550:
        return _token
    r = session.post(
        f"{BASE_URL}/auth/",
        json={"login": LOGIN, "password": PASSWORD},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    d = r.json()
    if d["status"] != "OK":
        raise RuntimeError(f"Auth failed: {d}")
    _token = d["response"]["token"]
    _token_time = time.time()
    return _token


def api_post(endpoint, payload=None):
    p = {"token": get_token()}
    if payload:
        p.update(payload)
    r = session.post(
        f"{BASE_URL}/{endpoint}/",
        json=p,
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


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


# ─── Фаза 1: Экспорт каталога и категорий ──────────────────────────────

def export_catalog():
    print("[1/4] Експорт каталогу...")
    products = []
    offset = 0
    while True:
        d = api_post("catalog/export", {"offset": offset, "limit": EXPORT_BATCH})
        if d["status"] not in ("OK", "WARNING"):
            raise RuntimeError(f"Export error: {d}")
        batch = d["response"]["products"]
        if not batch:
            break
        products.extend(batch)
        print(f"  {len(products)}...", end="\r", flush=True)
        if len(batch) < EXPORT_BATCH:
            break
        offset += EXPORT_BATCH
    print(f"  каталог: {len(products)} товарів     ")
    return products


def export_categories():
    print("       Експорт категорій...")
    seen = {}
    queue = [0]
    while queue:
        parent = queue.pop(0)
        try:
            d = api_post("pages/export", {"parent": parent})
        except Exception as e:
            print(f"  пропуск parent={parent}: {e}")
            continue
        if d.get("status") == "EMPTY":
            continue
        if d.get("status") != "OK":
            continue
        for p in d["response"]["pages"]:
            if p["id"] in seen:
                continue
            seen[p["id"]] = p
            queue.append(p["id"])
    print(f"  категорій: {len(seen)}")
    return list(seen.values())


# ─── Фаза 2: HTML-парсинг публичных страниц ────────────────────────────

def fetch(url):
    t0 = time.time()
    try:
        r = session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
        return r.status_code, r.text, r.url, round((time.time() - t0) * 1000), len(r.content)
    except Exception as e:
        return 0, str(e), url, 0, 0


def parse_seo(html):
    soup = BeautifulSoup(html, "lxml")
    head = soup.find("head") or soup
    body = soup.find("body") or soup

    def m(name=None, prop=None):
        if name:
            t = head.find("meta", attrs={"name": name})
        else:
            t = head.find("meta", attrs={"property": prop})
        return (t.get("content") if t else "") or ""

    info = {
        "title": (head.find("title").get_text().strip() if head.find("title") else ""),
        "meta_description": m(name="description"),
        "meta_keywords": m(name="keywords"),
        "meta_robots": m(name="robots"),
        "canonical": "",
        "og_title": m(prop="og:title"),
        "og_description": m(prop="og:description"),
        "og_image": m(prop="og:image"),
        "og_type": m(prop="og:type"),
        "h1": [h.get_text().strip() for h in body.find_all("h1")],
        "h1_count": len(body.find_all("h1")),
        "h2_count": len(body.find_all("h2")),
        "h3_count": len(body.find_all("h3")),
        "hreflang": [],
        "schema_jsonld": [],
        "schema_microdata": [],
        "images_no_alt": 0,
        "images_total": 0,
        "lang": (soup.find("html").get("lang") if soup.find("html") else ""),
    }
    can = head.find("link", rel="canonical")
    if can:
        info["canonical"] = can.get("href", "")
    for ln in head.find_all("link", rel="alternate"):
        if ln.get("hreflang"):
            info["hreflang"].append({"lang": ln.get("hreflang"), "href": ln.get("href", "")})
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "@type" in item:
                        info["schema_jsonld"].append(item["@type"])
            elif isinstance(data, dict):
                if "@type" in data:
                    info["schema_jsonld"].append(data["@type"])
                if "@graph" in data and isinstance(data["@graph"], list):
                    for it in data["@graph"]:
                        if isinstance(it, dict) and "@type" in it:
                            info["schema_jsonld"].append(it["@type"])
        except Exception:
            pass
    md = set()
    for el in soup.find_all(attrs={"itemtype": True}):
        t = (el.get("itemtype") or "").replace("https://schema.org/", "").replace("http://schema.org/", "")
        if t:
            md.add(t)
    info["schema_microdata"] = sorted(md)
    for img in body.find_all("img"):
        info["images_total"] += 1
        if not (img.get("alt") or "").strip():
            info["images_no_alt"] += 1
    # SEO-текст блок
    for sel in [".seo-text", ".description", ".text-content", "[class*=seoText]"]:
        el = soup.select_one(sel)
        if el:
            info["seo_text_length"] = len(strip_html(str(el)))
            break
    else:
        info["seo_text_length"] = 0
    return info


def html_audit(products):
    print("[2/4] HTML-парсинг публічних сторінок...")
    base = f"https://{DOMAIN}"

    # Из sitemap pages-sitemap.xml — все info + категории
    pages_sm_url = f"{base}/content/export/{DOMAIN}/pages-sitemap.xml"
    catalog_sm_url = f"{base}/content/export/{DOMAIN}/catalog-sitemap.xml"

    pages_urls = []
    catalog_urls = []
    try:
        sc, txt, _, _, _ = fetch(pages_sm_url)
        if sc == 200:
            pages_urls = re.findall(r"<loc>(.*?)</loc>", txt)
    except Exception:
        pass
    try:
        sc, txt, _, _, _ = fetch(catalog_sm_url)
        if sc == 200:
            catalog_urls = re.findall(r"<loc>(.*?)</loc>", txt)
    except Exception:
        pass

    print(f"  pages в sitemap: {len(pages_urls)}, catalog: {len(catalog_urls)}")

    pages_data = []
    for i, url in enumerate(pages_urls):
        sc, html, final, ms, size = fetch(url)
        if sc == 200:
            seo = parse_seo(html)
            seo.update({"url": url, "status": sc, "response_ms": ms, "html_size_kb": round(size/1024, 1)})
            pages_data.append(seo)
        else:
            pages_data.append({"url": url, "status": sc, "error": True})
        print(f"  [{i+1}/{len(pages_urls)}] {url.replace(base, '')}", end="\r", flush=True)

    # Сэмпл товаров — 10 случайных из каталога
    import random
    random.seed(42)
    sample = random.sample(catalog_urls, min(10, len(catalog_urls))) if catalog_urls else []
    products_data = []
    for url in sample:
        sc, html, final, ms, size = fetch(url)
        if sc == 200:
            seo = parse_seo(html)
            seo.update({"url": url, "status": sc, "response_ms": ms})
            products_data.append(seo)

    # Robots + sitemap главный
    sc_robots, robots_text, _, _, _ = fetch(f"{base}/robots.txt")
    sitemap_info = []
    sm_urls = [f"{base}/sitemap.xml"]
    if sc_robots == 200:
        sm_urls = []
        for line in robots_text.splitlines():
            if line.lower().startswith("sitemap:"):
                sm_urls.append(line.split(":", 1)[1].strip())
        if not sm_urls:
            sm_urls = [f"{base}/sitemap.xml"]
    for u in sm_urls:
        sc, txt, _, _, sz = fetch(u)
        sitemap_info.append({
            "url": u, "status": sc,
            "size_kb": round(sz/1024, 1),
            "url_count": txt.count("<url>") if sc == 200 else 0,
            "subsitemaps": txt.count("<sitemap>") if sc == 200 else 0,
        })

    print(f"\n  пройдено страниц: {len(pages_data)}, товарів: {len(products_data)}")

    return {
        "pages": pages_data,
        "products_sample": products_data,
        "robots": {"status": sc_robots, "size": len(robots_text) if sc_robots == 200 else 0},
        "sitemaps": sitemap_info,
        "totals": {
            "pages_in_sitemap": len(pages_urls),
            "catalog_in_sitemap": len(catalog_urls),
        },
    }


# ─── Фаза 3: Аудит товаров (deep) ──────────────────────────────────────

SPAM_WORDS = ["БЕСПЛАТНО", "ШОКИРУЮЩАЯ", "ГАРАНТИРОВАНО", "100%", "БЕЗКОШТОВНО", "ШОКУЮЧА", "ГАРАНТОВАНО"]
SALE_STICKER_KEYWORDS = ["распродаж", "знижк", "sale", "скидк"]


def audit_products(products):
    print("[3/4] Аудит товарів...")
    findings = defaultdict(list)
    by_parent = defaultdict(list)
    for p in products:
        by_parent[p.get("parent_article", p.get("article", ""))].append(p)

    seo_titles = defaultdict(list)
    seo_descs = defaultdict(list)
    h1s = defaultdict(list)
    titles = defaultdict(list)
    descs = defaultdict(list)
    slugs = defaultdict(list)

    char_keys_total = Counter()
    char_filled = Counter()
    char_total = Counter()

    desc_lengths = []
    short_lengths = []
    seo_title_lengths = []
    seo_desc_lengths = []

    brand_dist = Counter()
    presence_dist = Counter()
    icons_dist = Counter()
    marketplace_dist = Counter()

    now = datetime.now()
    main_count = 0
    mod_count = 0

    for p in products:
        article = p.get("article", "")
        parent_article = p.get("parent_article", "")
        is_main = (article == parent_article)
        if is_main:
            main_count += 1
        else:
            mod_count += 1

        title = get_text(p.get("title"))
        descr = strip_html(get_text(p.get("description")))
        short = strip_html(get_text(p.get("short_description")))
        seo_title = get_text(p.get("seo_title")).strip()
        seo_desc = get_text(p.get("seo_description")).strip()
        seo_keys = get_text(p.get("seo_keywords")).strip()
        h1 = get_text(p.get("h1_title")).strip()
        slug = (p.get("slug") or "").strip()

        if not p.get("display_in_showcase"):
            findings["hidden_products"].append({"article": article, "title": title})

        # Title quality
        if not title:
            findings["title_empty"].append({"article": article})
        else:
            problems = []
            if title != title.strip():
                problems.append("крайние пробелы")
            if "  " in title:
                problems.append("двойные пробелы")
            if title.isupper() and len(title) > 3:
                problems.append("ВСЕ КАПС")
            if title and title[0].islower():
                problems.append("со строчной")
            if re.search(r"<[^>]+>", title):
                problems.append("HTML в названии")
            if re.search(r"\(\s*\)", title):
                problems.append("пустые скобки")
            if len(title) > 200:
                problems.append(f"длинное ({len(title)})")
            if problems:
                findings["title_quality"].append({"article": article, "title": title, "issues": " | ".join(problems)})

        if is_main:
            # Descriptions
            if not descr:
                findings["description_empty"].append({"article": article, "title": title})
            elif len(descr) < 100:
                findings["description_short"].append({"article": article, "title": title, "len": len(descr)})
            desc_lengths.append(len(descr))

            if not short:
                findings["short_description_empty"].append({"article": article, "title": title})
            short_lengths.append(len(short))

            # SEO meta
            if not seo_title:
                findings["seo_title_empty"].append({"article": article, "title": title})
            else:
                seo_title_lengths.append(len(seo_title))
                if seo_title == title:
                    findings["seo_title_eq_title"].append({"article": article, "title": title})
                if len(seo_title) > 70:
                    findings["seo_title_long"].append({"article": article, "len": len(seo_title), "seo_title": seo_title})

            if not seo_desc:
                findings["seo_description_empty"].append({"article": article, "title": title})
            else:
                seo_desc_lengths.append(len(seo_desc))
                if len(seo_desc) > 170:
                    findings["seo_description_long"].append({"article": article, "len": len(seo_desc)})
                if len(seo_desc) < 70:
                    findings["seo_description_short"].append({"article": article, "len": len(seo_desc)})

            if not seo_keys:
                findings["seo_keywords_empty"].append({"article": article, "title": title})
            if not h1:
                findings["h1_empty"].append({"article": article, "title": title})

            # Дубликаты
            if seo_title:
                seo_titles[seo_title].append(article)
            if seo_desc:
                seo_descs[seo_desc].append(article)
            if h1:
                h1s[h1].append(article)
            if title:
                titles[title].append(article)
            if descr and len(descr) > 50:
                descs[descr[:200]].append(article)
            if slug:
                slugs[slug].append(article)

            # Slug
            if slug:
                if re.search(r"[А-Яа-яЁёІіЇїЄєҐґ]", slug):
                    findings["slug_cyrillic"].append({"article": article, "slug": slug})
                if re.search(r"[A-Z]", slug):
                    findings["slug_uppercase"].append({"article": article, "slug": slug})
                if "_" in slug:
                    findings["slug_underscore"].append({"article": article, "slug": slug})

            # Изображения
            imgs = p.get("images") or []
            gallery = p.get("gallery_common") or []
            total_imgs = (len(imgs) if isinstance(imgs, list) else 0) + (len(gallery) if isinstance(gallery, list) else 0)
            if total_imgs == 0:
                findings["no_images"].append({"article": article, "title": title})
            elif total_imgs == 1:
                findings["single_image"].append({"article": article, "title": title})

            # GTIN/MPN
            if not (p.get("gtin") or "").strip():
                findings["gtin_missing"].append({"article": article, "title": title})
            if not (p.get("mpn") or "").strip():
                findings["mpn_missing"].append({"article": article, "title": title})

            # uktzed
            if not (p.get("uktzed") or "").strip():
                findings["uktzed_empty"].append({"article": article, "title": title})

            # Описание content quality
            desc_html = get_text(p.get("description"))
            issues = []
            inline_styles = len(re.findall(r'style\s*=\s*"[^"]+"', desc_html))
            if inline_styles > 5:
                issues.append(f"inline-стилей: {inline_styles}")
            ext_links = re.findall(r'href\s*=\s*"https?://([^/"]+)', desc_html)
            ext_links = [d for d in ext_links if not d.endswith(DOMAIN) and not d.endswith("horoshop.ua")]
            if ext_links:
                issues.append(f"внешних ссылок: {len(ext_links)}")
            phones = re.findall(r"\+?38\s*\(?0\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", descr)
            emails = re.findall(r"[\w\.\-_]+@[\w\.\-_]+\.\w+", descr)
            if phones:
                issues.append(f"телефонов: {len(phones)}")
            if emails:
                issues.append(f"email: {len(emails)}")
            if len(descr) > 800 and len(re.findall(r"<h[23][\s>]", desc_html, re.I)) == 0:
                issues.append("нет h2/h3 в длинном описании")
            upper_desc = descr.upper()
            spam = [w for w in SPAM_WORDS if w in upper_desc]
            if spam:
                issues.append(f"спам-слова: {spam}")
            if issues:
                findings["description_quality"].append({"article": article, "title": title, "issues": " | ".join(issues)})

            # Marketplace_description
            mp_desc = strip_html(get_text(p.get("marketplace_description")))
            if not mp_desc:
                findings["marketplace_description_empty"].append({"article": article, "title": title})

            # Brand
            brand = p.get("brand") or {}
            bv = get_text(brand) if isinstance(brand, dict) else str(brand or "")
            brand_dist[bv or "(пусто)"] += 1
            if not bv:
                findings["brand_empty"].append({"article": article, "title": title})

            # Cross-sell
            if not (p.get("accessories") or []):
                findings["no_accessories"].append({"article": article, "title": title})
            if not (p.get("gifts") or []):
                findings["no_gifts"].append({"article": article, "title": title})
            if not (p.get("alt_parent") or []):
                findings["no_alt_parent"].append({"article": article, "title": title})

            # Marketplaces
            mks = p.get("export_to_marketplace") or []
            if not mks:
                findings["no_marketplaces"].append({"article": article, "title": title})
            else:
                for m in mks:
                    name = m.get("value") if isinstance(m, dict) else str(m)
                    marketplace_dist[name] += 1

            # Installments
            ip = p.get("installments_payment") or {}
            mp = p.get("monobank_installments_payment") or {}
            ip_id = ip.get("id", 1) if isinstance(ip, dict) else 1
            mp_id = mp.get("id", 1) if isinstance(mp, dict) else 1
            if ip_id == 1 and mp_id == 1:
                findings["installments_disabled"].append({"article": article, "title": title})

            # Sticker для скидки
            price = float(p.get("price") or 0)
            price_old = float(p.get("price_old") or 0)
            disc = p.get("discount") or 0
            if price_old > price > 0:
                icons = p.get("icons") or []
                icon_names = [(i.get("value", {}) if isinstance(i, dict) else {}) for i in icons]
                icon_names = [(n.get("ua") or n.get("ru") or "") if isinstance(n, dict) else str(n) for n in icon_names]
                icon_lower = " ".join(icon_names).lower()
                if not any(w in icon_lower for w in SALE_STICKER_KEYWORDS):
                    findings["no_sale_sticker"].append({
                        "article": article, "title": title,
                        "real_discount": round((price_old - price) / price_old * 100, 1),
                    })
                if disc in (0, "0", None):
                    findings["discount_unmarked"].append({
                        "article": article, "title": title,
                        "price": price, "price_old": price_old,
                        "real_discount": round((price_old - price) / price_old * 100, 1),
                    })

            # Прочее
            if price in (0, "0", None, ""):
                findings["price_zero"].append({"article": article, "title": title})

            # Characteristics
            chars = p.get("characteristics") or {}
            if isinstance(chars, dict):
                for k, v in chars.items():
                    char_keys_total[k] += 1
                    char_total[k] += 1
                    val = get_text(v) if isinstance(v, dict) else (str(v) if v else "")
                    if val and val.strip():
                        char_filled[k] += 1

            # Категория
            parent = p.get("parent")
            if not parent or (isinstance(parent, dict) and not parent.get("id")):
                findings["no_category"].append({"article": article, "title": title})

        # Countdown (для всех — родителей и модификаций)
        cd_end = p.get("countdown_end_time")
        cd_desc = get_text(p.get("countdown_description"))
        if cd_end and cd_end != "0000-00-00 00:00:00":
            try:
                d = datetime.strptime(cd_end, "%Y-%m-%d %H:%M:%S")
                if d < now:
                    findings["countdown_expired"].append({
                        "article": article, "title": title,
                        "ended": cd_end, "has_description": bool(cd_desc),
                    })
            except Exception:
                pass

        # Mod_title для модификаций
        if not is_main:
            mt = get_text(p.get("mod_title")).strip()
            if not mt:
                findings["mod_title_empty"].append({
                    "article": article, "parent": parent_article, "title": title,
                })

        # Presence
        pres = p.get("presence") or {}
        pv = get_text(pres) if isinstance(pres, dict) else str(pres or "")
        presence_dist[pv or "(пусто)"] += 1

    # Дубликаты
    dup = lambda d: {k: v for k, v in d.items() if len(v) > 1}
    findings["dup_seo_title"] = [{"value": k, "articles": v} for k, v in dup(seo_titles).items()]
    findings["dup_seo_description"] = [{"value": k[:120], "articles": v} for k, v in dup(seo_descs).items()]
    findings["dup_h1"] = [{"value": k, "articles": v} for k, v in dup(h1s).items()]
    findings["dup_title"] = [{"value": k, "articles": v} for k, v in dup(titles).items()]
    findings["dup_description"] = [{"value": k[:120], "articles": v} for k, v in dup(descs).items()]
    findings["dup_slug"] = [{"value": k, "articles": v} for k, v in dup(slugs).items()]

    char_fill = {
        ch: {"filled": char_filled[ch], "total": char_total[ch]}
        for ch in char_total
    }

    print(f"  знайдено: {len(findings)} типів проблем")

    return {
        "stats": {
            "total": len(products),
            "main_products": main_count,
            "modifications": mod_count,
            "hidden": len(findings.get("hidden_products", [])),
        },
        "char_fill_rate": char_fill,
        "brand_distribution": dict(brand_dist),
        "presence_distribution": dict(presence_dist),
        "marketplace_distribution": dict(marketplace_dist),
        "desc_length_stats": _stats(desc_lengths),
        "short_length_stats": _stats(short_lengths),
        "seo_title_length_stats": _stats(seo_title_lengths),
        "seo_desc_length_stats": _stats(seo_desc_lengths),
        "findings": dict(findings),
    }


def _stats(arr):
    if not arr:
        return {"count": 0}
    return {
        "count": len(arr),
        "min": min(arr), "max": max(arr),
        "avg": sum(arr) // len(arr),
    }


# ─── Фаза 4: Генерация REPORT.md ───────────────────────────────────────

def generate_report(products, categories, html, audit_data):
    print("[4/4] Формування REPORT.md...")
    f = audit_data["findings"]
    stats = audit_data["stats"]
    today = datetime.now().strftime("%Y-%m-%d")

    def n(key):
        return len(f.get(key, []))

    # HTML-аудит проблем категорий
    cat_pages = [p for p in html.get("pages", []) if not p.get("error")]

    # Классификация страниц
    INFO_KEYWORDS = ["pro-nas", "dohovir", "oplata", "obmin", "kontakt", "privacypolicy", "dohliad", "brands", "publichnoi", "polityka"]
    def is_home(p):
        return p["url"].rstrip("/") == f"https://{DOMAIN}"
    def is_info(p):
        return any(k in p["url"] for k in INFO_KEYWORDS)
    def is_category(p):
        return not is_home(p) and not is_info(p)

    # Длинные title — отдельно категории и инфо
    cat_long_title = [p for p in cat_pages if is_category(p) and len(p.get("title") or "") > 70]
    info_long_title = [p for p in cat_pages if is_info(p) and len(p.get("title") or "") > 70]

    cat_no_seotext = [p for p in cat_pages if is_category(p) and p.get("seo_text_length", 0) == 0]
    info_no_desc = [p for p in cat_pages if is_info(p) and not (p.get("meta_description") or "").strip()]
    pages_h1_dup = [p for p in cat_pages if p.get("h1_count", 0) > 1]
    home = next((p for p in cat_pages if is_home(p)), None)
    home_no_h1 = home and not home.get("h1")

    md = []
    md.append(f"# SEO-аудит {DOMAIN}\n")
    md.append(f"**Дата:** {today}")
    md.append(f"**Метод:** Horoshop API (`catalog/export`, `pages/export`) + HTML-парсинг публічних сторінок\n")

    md.append("## 📊 Сводка\n")
    md.append("| Метрика | Значення |")
    md.append("|---|---|")
    md.append(f"| Товарів усього | {stats['total']} |")
    md.append(f"| Головних модифікацій | {stats['main_products']} |")
    md.append(f"| Модифікацій | {stats['modifications']} |")
    md.append(f"| Прихованих | {stats['hidden']} |")
    md.append(f"| Категорій | {len(categories)} |")

    brands = audit_data.get("brand_distribution", {})
    if brands:
        top_brand = max(brands.items(), key=lambda x: x[1])
        md.append(f"| Бренд (топ) | {top_brand[0]} ({top_brand[1]} товарів) |")
    md.append(f"| Сторінок в sitemap | {html.get('totals',{}).get('pages_in_sitemap', '?')} |")

    md.append("\n## ✅ Що добре\n")
    if any(p.get("schema_microdata") for p in cat_pages):
        md.append("- Schema.org через microdata — реалізовано платформою")
    if any(p.get("og_title") for p in cat_pages):
        md.append("- OG-теги — на всіх типах сторінок")
    if html.get("robots", {}).get("status") == 200:
        md.append("- robots.txt — стандартний для платформи, не вимагає правок")
    if html.get("sitemaps"):
        sm_ok = [s for s in html["sitemaps"] if s.get("status") == 200]
        if sm_ok:
            md.append(f"- Sitemap.xml — {len(sm_ok)} файл(ів), генерується автоматично")

    sl_stats = audit_data.get("seo_title_length_stats", {})
    sd_stats = audit_data.get("seo_desc_length_stats", {})
    if sl_stats.get("avg") and 30 <= sl_stats["avg"] <= 70:
        md.append(f"- seo_title середня довжина {sl_stats['avg']} симв ({sl_stats['min']}-{sl_stats['max']}) — норма")
    if sd_stats.get("avg") and 100 <= sd_stats["avg"] <= 170:
        md.append(f"- seo_description середня довжина {sd_stats['avg']} симв ({sd_stats['min']}-{sd_stats['max']}) — норма")
    md.append("")

    # ── API fixes section ──────────────────────────────────────
    md.append("## 🟢 Що виправляється через API\n")
    fixes = []

    if n("countdown_expired"):
        fixes.append((
            f"### 1. Минулі акції (`countdown_end_time`) — {n('countdown_expired')} товарів",
            "На сторінці товара показується мертвий таймер або від'ємні значення. Підриває довіру.",
            "Запустити `apply_fixes.py --fix countdown` — обнулить дату або продовжити."
        ))
    if n("mod_title_empty"):
        fixes.append((
            f"### 2. Порожній `mod_title` — {n('mod_title_empty')} модифікацій",
            "У селекторі модифікацій користувач не бачить осмисленого імені (Двоспальний, Євро тощо).",
            "Запустити `apply_fixes.py --fix mod-title` — заповнить з ключової характеристики (rozmr/розмір)."
        ))
    if n("discount_unmarked"):
        fixes.append((
            f"### 3. `discount=0` при реальній знижці — {n('discount_unmarked')} товарів",
            "Хорошоп показує стікер -X% на основі поля `discount`. Якщо 0 — стікер прихований.",
            "`apply_fixes.py --fix discount` — порахує `(old-price)/old*100` і запише."
        ))
    if n("seo_title_empty") + n("seo_description_empty") + n("h1_empty") > 0:
        cnt = max(n("seo_title_empty"), n("seo_description_empty"), n("h1_empty"))
        fixes.append((
            f"### 4. Порожні SEO-поля — до {cnt} товарів",
            "SEO-шаблон дає дефолт, але унікальні мета-теги дають контроль над сніпетом і вищий CTR.",
            "`apply_fixes.py --fix seo --preview-only` → переглянути → `--fix seo` записати."
        ))
    if n("mpn_missing"):
        fixes.append((
            f"### 5. Відсутній MPN — {n('mpn_missing')} товарів",
            "Google Shopping/Rozetka/Facebook фіди вимагають MPN або GTIN. Без них модерація відхиляє.",
            "`apply_fixes.py --fix mpn --prefix XX` — генерує `XX-{article}` для всіх."
        ))
    if n("dup_description"):
        fixes.append((
            f"### 6. Дублікати description — {n('dup_description')} груп",
            "Google пеналізує дублі канонікалізацією → одна сторінка в індексі, інші втрачаються.",
            "`apply_fixes.py --fix dup-desc` — переписує під унікальні характеристики (превью обов'язкове)."
        ))
    if n("installments_disabled"):
        fixes.append((
            f"### 7. Оплата частинами вимкнена — {n('installments_disabled')} товарів",
            "Для середнього чека ≥500 грн розстрочка — стандартний канал конверсії в UA.",
            "`apply_fixes.py --fix installments` — увімкне Privat + Monobank."
        ))
    if n("no_sale_sticker"):
        fixes.append((
            f"### 8. Стікер «Распродажа» відсутній — {n('no_sale_sticker')} товарів зі знижкою",
            "Стікер — головний візуальний CTA в каталозі. Без нього скидка менш помітна.",
            "`apply_fixes.py --fix sticker-sale --sticker-name Распродажа` — додасть в `icons[]`."
        ))
    desc_quality_inline = sum(1 for x in f.get("description_quality", []) if "inline-стилей" in x.get("issues", ""))
    if desc_quality_inline:
        fixes.append((
            f"### 9. Inline-стилі в описах — {desc_quality_inline} товарів",
            "HTML захаращений `style=\"...\"` атрибутами. Не критично, але сповільнює рендер і конфліктує з темою.",
            "`apply_fixes.py --fix inline-styles --preview-only` → переглянути → запустити без `--preview-only`."
        ))
    if n("no_accessories") + n("no_alt_parent") > 5:
        fixes.append((
            f"### 10. Cross-sell не налаштовано — accessories/alt_parent у {n('no_accessories')} товарів",
            "Втрачений AOV (без блоку «з цим товаром купують») і внутрішня перелінковка (без альтернативних розділів типу «Хіти»).",
            "`apply_fixes.py --fix cross-sell --interactive` — потрібне обговорення стратегії що до чого прив'язувати."
        ))

    if not fixes:
        md.append("Жодних API-фіксів не потрібно — каталог чистий. ✅\n")
    else:
        for title, why, how in fixes:
            md.append(f"\n{title}\n")
            md.append(f"**Чому важливо:** {why}\n")
            md.append(f"**Як виправити:** {how}\n")

    # ── Admin fixes ────────────────────────────────────────────
    md.append("\n## 🟡 Що виправляється тільки в адмінці\n")
    admin_items = []

    if cat_long_title:
        admin_items.append((
            f"### A1. Довгі title у {len(cat_long_title)} категорій (>70 симв)",
            "Google ріже title у видачі до ~580 px (~65 симв кирилиці). Хвіст шаблону губиться.",
            "**Маркетинг → SEO → SEO шаблони → Категорії** — скоротити шаблон до ~50-60 симв.",
            [p["url"].replace(f"https://{DOMAIN}", "") for p in cat_long_title[:5]],
        ))
    if info_long_title:
        admin_items.append((
            f"### A2. Довгі title у {len(info_long_title)} інфо-сторінок (>70 симв)",
            "Те саме що для категорій — Google обрізає в SERP.",
            "Кожна інфо-сторінка редагується окремо: **Сторінки сайту → [сторінка] → SEO заголовок**.",
            [p["url"].replace(f"https://{DOMAIN}", "") for p in info_long_title[:5]],
        ))
    if info_no_desc:
        admin_items.append((
            f"### B. Інфо-сторінки без description ({len(info_no_desc)} шт)",
            "Без description Google генерує сниппет з тексту — зазвичай невдало.",
            "**Сторінки сайту → Інформаційні сторінки → [сторінка] → SEO**",
            [p["url"].replace(f"https://{DOMAIN}", "") for p in info_no_desc],
        ))
    if pages_h1_dup:
        admin_items.append((
            f"### C. Кілька `<h1>` на сторінці ({len(pages_h1_dup)} шт)",
            "Розмиває семантику для Google. Має бути один h1 на сторінку.",
            "Перевір SEO-текст і шаблон сторінки — скоріш за все продубльовано.",
            [p["url"].replace(f"https://{DOMAIN}", "") for p in pages_h1_dup],
        ))
    if home_no_h1:
        admin_items.append((
            "### D. Головна без `<h1>`",
            "h1 — головний текстовий сигнал теми. Без нього головна втрачає вагу за брендом і основною категорією.",
            "**Редактор дизайну → Головна → блок із заголовком**",
            [],
        ))
    if n("hidden_products"):
        admin_items.append((
            f"### E. Приховані товари ({n('hidden_products')} шт)",
            "Сміття в API. Якщо колись були відкриті — можуть лишитися в індексі Google як 404.",
            "**Каталог → Товар** — повернути в продаж, перевести в архів або видалити.",
            [],
        ))
    if n("uktzed_empty"):
        admin_items.append((
            f"### F. Порожній УКТ ВЕД ({n('uktzed_empty')} товарів)",
            "Не для SEO. Потрібно для ПРРО Checkbox (чек), імпорту/експорту, фідів. Через API не редагується.",
            "**Каталог → Товар → УКТ ВЕД** (вручну або CSV-імпортом).",
            [],
        ))
    if cat_no_seotext:
        admin_items.append((
            f"### G. Категорії без SEO-тексту ({len(cat_no_seotext)} шт)",
            "SEO-текст — основний контент для ранжування за комерційними запитами категорії.",
            "**Каталог → Категорія → SEO-текст** — додати блок 800-2000 симв з h2/h3.",
            [p["url"].replace(f"https://{DOMAIN}", "") for p in cat_no_seotext[:5]],
        ))

    if not admin_items:
        md.append("Адмінських задач немає — все ок або виправляється через API. ✅\n")
    else:
        for title, why, where, examples in admin_items:
            md.append(f"\n{title}\n")
            md.append(f"**Чому важливо:** {why}\n")
            md.append(f"**Де правити:** {where}\n")
            if examples:
                md.append("**Приклади:**")
                for e in examples:
                    md.append(f"- `{e}`")
                md.append("")

    md.append("\n## 🚫 Що НЕ змінюємо\n")
    md.append("- robots.txt — стандартний для платформи")
    md.append("- Sitemap.xml — генерується автоматично")
    md.append("- Schema/microdata — реалізована платформою")
    md.append("- URL-формули, hreflang, canonical — налаштовано платформою")
    md.append("- Slug з `/{id}` в кінці — це формат Хорошопа\n")

    # Дополнительные заметки
    md.append("## 📝 Додаткові спостереження\n")
    char_fill = audit_data.get("char_fill_rate", {})
    if char_fill:
        md.append("**Заповнення характеристик** (для головних товарів):")
        for ch, v in sorted(char_fill.items(), key=lambda x: -x[1]["filled"])[:10]:
            pct = v["filled"] * 100 // v["total"] if v["total"] else 0
            mark = "🟢" if pct >= 80 else "🟡" if pct >= 50 else "🔴"
            md.append(f"- {mark} `{ch}`: {v['filled']}/{v['total']} ({pct}%)")
        md.append("")

    Path("REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  REPORT.md: {OUT / 'REPORT.md'}")


def main():
    print(f"=== Аудит {DOMAIN} ===\n")

    products = export_catalog()
    Path("catalog.json").write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")

    categories = export_categories()
    Path("categories.json").write_text(json.dumps(categories, ensure_ascii=False, indent=2), encoding="utf-8")

    html = html_audit(products)
    Path("html_audit.json").write_text(json.dumps(html, ensure_ascii=False, indent=2), encoding="utf-8")

    audit_data = audit_products(products)
    Path("findings.json").write_text(json.dumps(audit_data, ensure_ascii=False, indent=2), encoding="utf-8")

    generate_report(products, categories, html, audit_data)

    f = audit_data["findings"]
    print("\n━━━ TL;DR ━━━")
    print(f"  Товарів: {audit_data['stats']['total']} (головних {audit_data['stats']['main_products']}, модифікацій {audit_data['stats']['modifications']})")
    print(f"  Категорій: {len(categories)}")
    counts = sorted(((k, len(v) if isinstance(v, list) else 0) for k, v in f.items()), key=lambda x: -x[1])[:10]
    print("  Топ знахідок:")
    for k, c in counts:
        print(f"    {c:5d}  {k}")


if __name__ == "__main__":
    main()

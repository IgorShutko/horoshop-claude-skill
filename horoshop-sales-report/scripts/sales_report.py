#!/usr/bin/env python3
"""Horoshop sales report — выгрузка заказов через `orders/get`, расчёты, SALES_REPORT.md.

Использование:
  python3 sales_report.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Конфиг через env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD

По умолчанию — последние 30 дней.

Выручка считается ТОЛЬКО по доставленным заказам (status=3).
"""

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")

if not all([DOMAIN, LOGIN, PASSWORD]):
    print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы", file=sys.stderr)
    sys.exit(1)

BASE_URL = f"https://{DOMAIN}/api"
PAGE_SIZE = 500
HTTP_TIMEOUT = 90

# Стандартные статусы Horoshop. Если у магазина кастомные —
# скилл выводит подсказку про `orders/get_available_statuses`.
STATUS_LABELS = {
    1: "Новый",
    2: "В обработке",
    3: "Доставлен",
    4: "Не доставлен / отменён",
    6: "Доставляется",
}
STATUS_DELIVERED = 3
STATUS_CANCELLED = 4

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Horoshop Sales Report)"})

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


def fetch_orders(date_from, date_to):
    """Пагинированная выгрузка заказов. Параметры даты в формате YYYY-MM-DD."""
    orders = []
    offset = 0
    print(f"  с {date_from} по {date_to} (включительно)")
    while True:
        r = session.post(
            f"{BASE_URL}/orders/get/",
            json={
                "token": get_token(),
                "from": date_from,
                "to": date_to,
                "offset": offset,
                "limit": PAGE_SIZE,
            },
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
        if d.get("status") == "EMPTY":
            break
        if d.get("status") != "OK":
            raise RuntimeError(f"orders/get error: {d}")
        batch = d["response"]["orders"]
        if not batch:
            break
        orders.extend(batch)
        print(f"  выгружено: {len(orders)}", end="\r", flush=True)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print(f"  выгружено: {len(orders)} заказов     ")
    return orders


# ─── Расчёты ───────────────────────────────────────────────────────────────

def parse_date(s):
    """Парсит stat_created в datetime."""
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def status_breakdown(orders):
    """Распределение по статусам."""
    c = Counter()
    for o in orders:
        c[o.get("stat_status")] += 1
    return c


def overall_stats(orders):
    """Общая статистика."""
    delivered = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]
    revenue = sum(float(o.get("total_sum") or 0) for o in delivered)
    avg_check = revenue / len(delivered) if delivered else 0
    avg_qty = (
        sum(int(o.get("total_quantity") or 0) for o in delivered) / len(delivered)
        if delivered else 0
    )
    cancelled = sum(1 for o in orders if o.get("stat_status") == STATUS_CANCELLED)

    # Потенциальная выручка — статусы кроме «не доставлен/отменён»
    in_pipeline = [o for o in orders if o.get("stat_status") not in (STATUS_CANCELLED,)]
    potential_revenue = sum(float(o.get("total_sum") or 0) for o in in_pipeline)

    avg_check_all = (
        sum(float(o.get("total_sum") or 0) for o in orders) / len(orders)
        if orders else 0
    )

    return {
        "total_orders": len(orders),
        "delivered": len(delivered),
        "delivered_pct": len(delivered) / len(orders) * 100 if orders else 0,
        "cancelled": cancelled,
        "cancelled_pct": cancelled / len(orders) * 100 if orders else 0,
        "revenue": revenue,
        "potential_revenue": potential_revenue,
        "in_pipeline": len(in_pipeline),
        "avg_check": avg_check,
        "avg_check_all_statuses": avg_check_all,
        "avg_quantity": avg_qty,
        "status_distribution": dict(status_breakdown(orders)),
    }


def daily_dynamics(orders, only_delivered=True):
    """По дням: заказы / выручка / AOV. Только доставленные по умолчанию."""
    target = orders
    if only_delivered:
        target = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]

    by_day = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for o in target:
        d = parse_date(o.get("stat_created", ""))
        if not d:
            continue
        key = d.strftime("%Y-%m-%d")
        by_day[key]["orders"] += 1
        by_day[key]["revenue"] += float(o.get("total_sum") or 0)

    rows = []
    for day in sorted(by_day):
        v = by_day[day]
        avg = v["revenue"] / v["orders"] if v["orders"] else 0
        rows.append({"date": day, "orders": v["orders"], "revenue": v["revenue"], "aov": avg})
    return rows


def weekly_dynamics(orders, only_delivered=True):
    """По неделям (ISO week): заказы / выручка / AOV."""
    target = orders
    if only_delivered:
        target = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]

    by_week = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for o in target:
        d = parse_date(o.get("stat_created", ""))
        if not d:
            continue
        # ISO week: YYYY-Www
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        by_week[key]["orders"] += 1
        by_week[key]["revenue"] += float(o.get("total_sum") or 0)

    rows = []
    for week in sorted(by_week):
        v = by_week[week]
        avg = v["revenue"] / v["orders"] if v["orders"] else 0
        rows.append({"week": week, "orders": v["orders"], "revenue": v["revenue"], "aov": avg})
    return rows


def monthly_dynamics(orders, only_delivered=True):
    """По месяцам."""
    target = orders
    if only_delivered:
        target = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]

    by_month = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for o in target:
        d = parse_date(o.get("stat_created", ""))
        if not d:
            continue
        key = d.strftime("%Y-%m")
        by_month[key]["orders"] += 1
        by_month[key]["revenue"] += float(o.get("total_sum") or 0)

    rows = []
    for month in sorted(by_month):
        v = by_month[month]
        avg = v["revenue"] / v["orders"] if v["orders"] else 0
        rows.append({"month": month, "orders": v["orders"], "revenue": v["revenue"], "aov": avg})
    return rows


def abc_analysis(orders):
    """ABC товаров по выручке. Только доставленные.

    A: top 80% revenue
    B: next 15%
    C: last 5%
    """
    delivered = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]
    by_article = defaultdict(lambda: {"title": "", "revenue": 0.0, "qty": 0, "orders": 0})
    for o in delivered:
        for p in o.get("products") or []:
            # пропускаем подарки/составные части комплекта (они price=0 или зависимы)
            if p.get("type") in ("gift", "set_item"):
                continue
            article = p.get("article") or ""
            if not article:
                continue
            entry = by_article[article]
            entry["title"] = p.get("title", "") or entry["title"]
            entry["revenue"] += float(p.get("total_price") or 0)
            entry["qty"] += int(p.get("quantity") or 0)
            entry["orders"] += 1

    items = sorted(by_article.items(), key=lambda x: -x[1]["revenue"])
    total_revenue = sum(it[1]["revenue"] for it in items)

    if total_revenue == 0:
        return [], total_revenue

    cumulative = 0
    classified = []
    for article, data in items:
        cumulative += data["revenue"]
        share = cumulative / total_revenue
        if share <= 0.80:
            grade = "A"
        elif share <= 0.95:
            grade = "B"
        else:
            grade = "C"
        classified.append({
            "article": article,
            "title": data["title"],
            "revenue": data["revenue"],
            "qty": data["qty"],
            "orders": data["orders"],
            "share_pct": data["revenue"] / total_revenue * 100,
            "cumulative_pct": share * 100,
            "grade": grade,
        })
    return classified, total_revenue


def utm_breakdown(orders):
    """Группировка по utm_source доставленных заказов."""
    delivered = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]
    by_source = defaultdict(lambda: {"orders": 0, "revenue": 0.0})

    DIRECT_VALUES = {"", "(none)", "none", "(direct)", "direct", "(direct/none)"}

    for o in delivered:
        a = o.get("analytics") or {}
        src_raw = (a.get("utm_source") or "").strip().lower()
        # Объединяем все «прямые» / отсутствующие источники
        if src_raw in DIRECT_VALUES:
            src = "(direct/none)"
        # Шаблонные плейсхолдеры тоже считаем как direct
        elif "{{" in src_raw and "}}" in src_raw:
            src = "(direct/none)"
        else:
            src = src_raw
        by_source[src]["orders"] += 1
        by_source[src]["revenue"] += float(o.get("total_sum") or 0)

    rows = []
    for src, v in sorted(by_source.items(), key=lambda x: -x[1]["revenue"]):
        avg = v["revenue"] / v["orders"] if v["orders"] else 0
        rows.append({"source": src, "orders": v["orders"], "revenue": v["revenue"], "aov": avg})
    return rows


def _safe_title(field, fallback="(не указан)"):
    """Достаём title из {id, title} структуры, либо fallback."""
    if not field:
        return fallback
    if isinstance(field, dict):
        t = (field.get("title") or "").strip()
        return t or fallback
    return (str(field) or "").strip() or fallback


def payment_breakdown(orders):
    delivered = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]
    by_pay = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for o in delivered:
        title = _safe_title(o.get("payment_type"))
        by_pay[title]["orders"] += 1
        by_pay[title]["revenue"] += float(o.get("total_sum") or 0)
    return sorted(
        [{"name": k, "orders": v["orders"], "revenue": v["revenue"]}
         for k, v in by_pay.items()],
        key=lambda x: -x["revenue"]
    )


def delivery_breakdown(orders):
    delivered = [o for o in orders if o.get("stat_status") == STATUS_DELIVERED]
    by_d = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for o in delivered:
        title = _safe_title(o.get("delivery_type"))
        by_d[title]["orders"] += 1
        by_d[title]["revenue"] += float(o.get("total_sum") or 0)
    return sorted(
        [{"name": k, "orders": v["orders"], "revenue": v["revenue"]}
         for k, v in by_d.items()],
        key=lambda x: -x["revenue"]
    )


# ─── Спарклайны ─────────────────────────────────────────────────────────────

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values):
    if not values:
        return ""
    mn = min(values)
    mx = max(values)
    if mx == mn:
        return SPARK_CHARS[len(SPARK_CHARS) // 2] * len(values)
    rng = mx - mn
    out = []
    for v in values:
        idx = int((v - mn) / rng * (len(SPARK_CHARS) - 1))
        out.append(SPARK_CHARS[idx])
    return "".join(out)


def fmt_money(amount):
    return f"{int(round(amount)):,}".replace(",", " ")


# ─── Генерация отчёта ──────────────────────────────────────────────────────

def generate_report(orders, date_from, date_to, stats, status_dist, daily, weekly, monthly,
                    abc, total_abc_revenue, utm, payments, deliveries):
    md = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    md.append(f"# Звіт продажів `{DOMAIN}`\n")
    md.append(f"**Період:** {date_from} — {date_to}  ")
    md.append(f"**Згенеровано:** {today}\n")

    # ── Сводка ─────────────────────────────────────────────────────
    md.append("## 📊 Сводка\n")
    md.append("| Метрика | Значение |")
    md.append("|---|---|")
    md.append(f"| Всего заказов | {stats['total_orders']} |")
    md.append(f"| Доставлено (status=3) | {stats['delivered']} ({stats['delivered_pct']:.1f}%) |")
    md.append(f"| Отменено / не доставлено (status=4) | {stats['cancelled']} ({stats['cancelled_pct']:.1f}%) |")
    md.append(f"| В воронке (новые/в обработке/доставляется) | {stats['in_pipeline'] - stats['delivered']} |")
    md.append(f"| **Зафиксированная выручка** (доставленные) | **{fmt_money(stats['revenue'])} грн** |")
    md.append(f"| **Потенциальная выручка** (всё кроме отменённых) | **{fmt_money(stats['potential_revenue'])} грн** |")
    md.append(f"| **Средний чек** (доставленные) | **{fmt_money(stats['avg_check'])} грн** |")
    md.append(f"| Средний чек (все статусы) | {fmt_money(stats['avg_check_all_statuses'])} грн |")
    md.append(f"| Среднее количество товаров в заказе | {stats['avg_quantity']:.2f} |")
    md.append("")

    # Если % новых > 50% — магазин не закрывает статусы. Дисклеймер.
    new_pct = status_dist.get(1, 0) / stats["total_orders"] * 100 if stats["total_orders"] else 0
    if new_pct > 50:
        md.append(f"> ⚠️ **{new_pct:.0f}% заказов в статусе «Новый»** — магазин не закрывает статусы автоматически или не использует workflow обработки. Для корректного представления о реальной выручке смотрите «Потенциальную выручку» — это деньги в воронке, минус подтверждённые отмены.\n")

    # ── Распределение по статусам ──────────────────────────────────
    md.append("## 📋 Заказы по статусам\n")
    md.append("| Статус | Заказов | % |")
    md.append("|---|---|---|")
    for status_id, count in sorted(status_dist.items(), key=lambda x: -x[1]):
        label = STATUS_LABELS.get(status_id, f"Кастомный (id={status_id})")
        pct = count / stats["total_orders"] * 100 if stats["total_orders"] else 0
        md.append(f"| {label} (id={status_id}) | {count} | {pct:.1f}% |")
    md.append("")
    md.append("> Если у магазина кастомные статусы — посмотри их через `orders/get_available_statuses`.\n")

    # ── Динамика по месяцам ────────────────────────────────────────
    if monthly and len(monthly) > 1:
        md.append("## 📈 Динамика по месяцам (только доставленные)\n")
        revs = [m["revenue"] for m in monthly]
        ords = [m["orders"] for m in monthly]
        md.append(f"Выручка: `{sparkline(revs)}`")
        md.append(f"Заказы:  `{sparkline(ords)}`\n")
        md.append("| Месяц | Заказов | Выручка | AOV |")
        md.append("|---|---|---|---|")
        for m in monthly:
            md.append(f"| {m['month']} | {m['orders']} | {fmt_money(m['revenue'])} | {fmt_money(m['aov'])} |")
        md.append("")

    # ── Динамика по неделям ────────────────────────────────────────
    if weekly:
        md.append("## 📈 Динамика по неделям (только доставленные)\n")
        revs = [w["revenue"] for w in weekly]
        ords = [w["orders"] for w in weekly]
        md.append(f"Выручка: `{sparkline(revs)}`")
        md.append(f"Заказы:  `{sparkline(ords)}`\n")
        md.append("| Неделя | Заказов | Выручка | AOV |")
        md.append("|---|---|---|---|")
        for w in weekly:
            md.append(f"| {w['week']} | {w['orders']} | {fmt_money(w['revenue'])} | {fmt_money(w['aov'])} |")
        md.append("")

    # ── Топ-30 дней (если много дней — иначе все) ──────────────────
    if daily:
        show_daily = daily if len(daily) <= 35 else daily[-30:]
        md.append(f"## 📈 Динамика по дням (только доставленные, последние {len(show_daily)} дней)\n")
        revs = [d["revenue"] for d in show_daily]
        md.append(f"Выручка: `{sparkline(revs)}`\n")
        md.append("| Дата | Заказов | Выручка | AOV |")
        md.append("|---|---|---|---|")
        for d in show_daily:
            md.append(f"| {d['date']} | {d['orders']} | {fmt_money(d['revenue'])} | {fmt_money(d['aov'])} |")
        md.append("")

    # ── ABC-анализ ─────────────────────────────────────────────────
    if abc:
        groups = {"A": [], "B": [], "C": []}
        for item in abc:
            groups[item["grade"]].append(item)

        md.append("## 🏆 ABC-анализ товаров (Парето 80/15/5)\n")
        md.append(f"**Базис:** выручка по доставленным = **{fmt_money(total_abc_revenue)} грн**, всего товаров продавалось — **{len(abc)}**\n")

        md.append("| Группа | Товаров | Доля выручки | Что это значит |")
        md.append("|---|---|---|---|")
        for g, items in groups.items():
            share = sum(it["revenue"] for it in items) / total_abc_revenue * 100 if total_abc_revenue else 0
            comment = {
                "A": "Двигатели бизнеса. Не давать выйти из стока, защищать рекламой.",
                "B": "Средний слой. Кандидаты в A при правильной поддержке.",
                "C": "Хвост. Иногда — мёртвый груз. Часто стоит архивировать или ребрендить.",
            }[g]
            md.append(f"| **{g}** | {len(items)} ({len(items)/len(abc)*100:.1f}%) | {share:.1f}% | {comment} |")
        md.append("")

        # Топ группы A
        if groups["A"]:
            md.append("### Группа A — топ-20\n")
            md.append("| # | Артикул | Название | Выручка | Заказов | Шт. | Доля % |")
            md.append("|---|---|---|---|---|---|---|")
            for i, it in enumerate(groups["A"][:20], 1):
                md.append(f"| {i} | `{it['article']}` | {it['title']} | {fmt_money(it['revenue'])} | {it['orders']} | {it['qty']} | {it['share_pct']:.1f}% |")
            md.append("")

        # Топ-10 в группе C для проверки (мёртвый груз)
        if groups["C"]:
            md.append("### Группа C — топ-10 (мёртвый груз? проверь нужны ли)\n")
            md.append("| Артикул | Название | Выручка | Заказов |")
            md.append("|---|---|---|---|")
            for it in groups["C"][:10]:
                md.append(f"| `{it['article']}` | {it['title']} | {fmt_money(it['revenue'])} | {it['orders']} |")
            md.append("")

    # ── Топ-10 по количеству ────────────────────────────────────────
    if abc:
        md.append("## 🥇 Топ-10 товаров по количеству продаж\n")
        top_qty = sorted(abc, key=lambda x: -x["qty"])[:10]
        md.append("| # | Артикул | Название | Шт. | Заказов | Выручка |")
        md.append("|---|---|---|---|---|---|")
        for i, it in enumerate(top_qty, 1):
            md.append(f"| {i} | `{it['article']}` | {it['title']} | {it['qty']} | {it['orders']} | {fmt_money(it['revenue'])} |")
        md.append("")

    # ── UTM-источники ──────────────────────────────────────────────
    if utm:
        md.append("## 🌐 UTM-источники (только доставленные)\n")
        md.append("| Source | Заказов | Выручка | AOV |")
        md.append("|---|---|---|---|")
        for u in utm:
            md.append(f"| {u['source']} | {u['orders']} | {fmt_money(u['revenue'])} | {fmt_money(u['aov'])} |")
        none_share = next(
            (u["orders"] for u in utm if u["source"] == "(direct/none)"), 0
        ) / sum(u["orders"] for u in utm) * 100 if utm else 0
        if none_share > 30:
            md.append(f"\n> ⚠️ **{none_share:.0f}% заказов без UTM** — возможна утечка трекинга. Проверь UTM-разметку в рекламе и трекинг прямых заходов через `analytics.utm_source`.")
        md.append("")

    # ── Способы оплаты / доставки ──────────────────────────────────
    if payments:
        md.append("## 💳 Способы оплаты (только доставленные)\n")
        md.append("| Способ | Заказов | Выручка |")
        md.append("|---|---|---|")
        for p in payments:
            md.append(f"| {p['name']} | {p['orders']} | {fmt_money(p['revenue'])} |")
        md.append("")

    if deliveries:
        md.append("## 🚚 Способы доставки (только доставленные)\n")
        md.append("| Способ | Заказов | Выручка |")
        md.append("|---|---|---|")
        for d in deliveries:
            md.append(f"| {d['name']} | {d['orders']} | {fmt_money(d['revenue'])} |")
        md.append("")

    # ── Что обратить внимание ──────────────────────────────────────
    md.append("## ⚠️ На что обратить внимание\n")
    flags = []

    # 100% (или почти 100%) заказов в одном статусе — самая серьёзная аномалия
    status_dist = stats.get("status_distribution") or status_breakdown(orders)
    total_o = sum(status_dist.values())
    if total_o > 0:
        for st_id, cnt in status_dist.items():
            pct = cnt / total_o * 100
            if pct >= 95 and st_id not in (STATUS_DELIVERED,):
                # 95%+ в одном НЕ-доставленном статусе — критично
                st_name = {1: "Новый", 2: "В обработке", 4: "Не доставлен", 6: "Доставляется"}.get(st_id, f"id={st_id}")
                flags.append(
                    f"- 🔴 **{pct:.0f}% заказов в статусе «{st_name}»** — критическая аномалия. "
                    f"Магазин не закрывает заказы статусом «Доставлен» (id=3), либо менеджеры "
                    f"не обрабатывают заказы. Выручка ({fmt_money(stats['revenue'])}) посчитана "
                    f"только по статусу 3 — реальная выручка не отображается. "
                    f"Проверь процесс обработки заказов в админке."
                )
                break

    if stats["cancelled_pct"] > 25:
        flags.append(f"- **Высокий % отмен ({stats['cancelled_pct']:.1f}%)** — норма до 15-20%. Проверь воронку: качество лидов, скорость обработки, проблемы с подтверждением.")
    if abc and len(abc) > 10:
        a_count = sum(1 for it in abc if it["grade"] == "A")
        if a_count <= 3:
            flags.append(f"- **Концентрация в группе A ({a_count} товара(ов) делают 80% выручки)** — если один из них выйдет из стока или его обгонит конкурент, серьёзная просадка.")
    if weekly and len(weekly) >= 5:
        # Берём последние 4 ПОЛНЫЕ недели (исключаем последнюю — она часто неполная)
        last_4 = [w["revenue"] for w in weekly[-5:-1]]
        if last_4[-1] < last_4[0] * 0.8 and last_4[0] > 0:
            drop_pct = (1 - last_4[-1] / last_4[0]) * 100
            flags.append(f"- **Выручка падает: -{drop_pct:.0f}% за 4 полных недели** (без учёта текущей неполной) — копай в чём дело (рекламные кампании, сезонность, конкуренты, проблемы с сайтом).")
        if all(b < a for a, b in zip(last_4[:-1], last_4[1:])) and len(last_4) >= 3:
            flags.append("- Выручка падает **3 полные недели подряд** — стабильный негативный тренд.")
    if utm:
        none_orders = sum(u["orders"] for u in utm if u["source"] == "(direct/none)")
        total_o = sum(u["orders"] for u in utm)
        if total_o and none_orders / total_o > 0.5:
            flags.append(f"- **>50% заказов без UTM-разметки** — трекинг рекламы сломан или большой % SEO/прямых заходов. Уточни через GA.")

    if flags:
        for fl in flags:
            md.append(fl)
    else:
        md.append("Серьёзных аномалий не найдено. ✅")

    md.append("")
    # ── Брендовый футер ────────────────────────────────────────────
    md.append("---\n")
    md.append("📈 *Згенеровано скілом [horoshop-sales-report](https://github.com/IgorShutko/horoshop-claude-skill) — створено агенцією [Target+](https://www.targetplus-agency.com/) (performance-маркетинг для UA e-commerce).*  ")
    md.append("*Допомога з впровадженням рекомендацій? [TG @shutko_ads](https://t.me/shutko_ads) або [заявка через сайт](https://www.targetplus-agency.com/).*")

    return "\n".join(md)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Horoshop sales report")
    today = datetime.now().date()
    default_from = (today - timedelta(days=30)).isoformat()
    default_to = today.isoformat()

    parser.add_argument("--from", dest="date_from", default=default_from, help=f"Дата начала (YYYY-MM-DD). По умолчанию: {default_from}")
    parser.add_argument("--to", dest="date_to", default=default_to, help=f"Дата конца (YYYY-MM-DD). По умолчанию: {default_to}")
    args = parser.parse_args()

    print(f"=== Sales report {DOMAIN} ===\n")
    print("[1/3] Выгрузка заказов через `orders/get`...")
    orders = fetch_orders(args.date_from, args.date_to)
    Path("orders.json").write_text(json.dumps(orders, ensure_ascii=False), encoding="utf-8")

    if not orders:
        print(f"\nЗа период {args.date_from} — {args.date_to} заказов не найдено.")
        return

    print("\n[2/3] Расчёты...")
    stats = overall_stats(orders)
    status_dist = status_breakdown(orders)
    daily = daily_dynamics(orders)
    weekly = weekly_dynamics(orders)
    monthly = monthly_dynamics(orders)
    abc, total_abc_revenue = abc_analysis(orders)
    utm = utm_breakdown(orders)
    payments = payment_breakdown(orders)
    deliveries = delivery_breakdown(orders)

    print("[3/3] Формирование SALES_REPORT.md...")
    report = generate_report(
        orders, args.date_from, args.date_to, stats, status_dist,
        daily, weekly, monthly, abc, total_abc_revenue, utm, payments, deliveries,
    )
    Path("SALES_REPORT.md").write_text(report, encoding="utf-8")

    # Также CSV ABC для удобства
    import csv
    if abc:
        with open("abc.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["grade", "article", "title", "revenue", "qty", "orders", "share_pct", "cumulative_pct"])
            for it in abc:
                w.writerow([it["grade"], it["article"], it["title"], round(it["revenue"]),
                            it["qty"], it["orders"], round(it["share_pct"], 2),
                            round(it["cumulative_pct"], 2)])

    # ── TL;DR в консоль ────────────────────────────────────────────
    print("\n━━━ TL;DR ━━━")
    print(f"  Период: {args.date_from} — {args.date_to}")
    print(f"  Заказов: {stats['total_orders']} (доставлено: {stats['delivered']}, отменено: {stats['cancelled']})")
    print(f"  Выручка: {fmt_money(stats['revenue'])} грн")
    print(f"  Средний чек (доставленные): {fmt_money(stats['avg_check'])} грн")
    if abc:
        a_count = sum(1 for it in abc if it["grade"] == "A")
        print(f"  ABC: A={a_count}, B={sum(1 for it in abc if it['grade']=='B')}, C={sum(1 for it in abc if it['grade']=='C')}")
        if abc[:3]:
            print(f"  Топ-3 по выручке:")
            for it in abc[:3]:
                print(f"    {it['article']}: {fmt_money(it['revenue'])} грн ({it['title'][:60]})")
    print(f"\nФайлы: SALES_REPORT.md, orders.json, abc.csv")


if __name__ == "__main__":
    main()

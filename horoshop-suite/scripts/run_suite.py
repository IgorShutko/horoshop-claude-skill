#!/usr/bin/env python3
"""Horoshop Suite — оркестратор всех скиллов.

Использование:
  python3 run_suite.py [--skip photo,consistency]
                       [--only audit,sales]
                       [--from 2026-04-01 --to 2026-04-30]
                       [--site-url https://example.com.ua]

Конфиг env: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

DOMAIN = os.getenv("HOROSHOP_DOMAIN")
LOGIN = os.getenv("HOROSHOP_LOGIN")
PASSWORD = os.getenv("HOROSHOP_PASSWORD")

SKILLS_DIR = Path.home() / ".claude" / "skills"

# Имя скилла → (имя командной части, путь к скрипту, поддерживает --from-file)
SKILLS = {
    "audit":       ("horoshop-full-audit",        "scripts/audit.py",                False),  # выгружает сам
    "sales":       ("horoshop-sales-report",      "scripts/sales_report.py",         False),  # отдельный API
    "gaps":        ("horoshop-content-fill",      "scripts/find_gaps.py",            True),
    "photo":       ("horoshop-photo-audit",       "scripts/photo_audit.py",          True),
    "text":        ("horoshop-text-quality",      "scripts/text_quality.py",         True),
    "consistency": ("horoshop-consistency",       "scripts/check_consistency.py",    True),
    "design":      ("horoshop-design-extract",    "scripts/extract.py",              False),  # парсит публичный сайт
}


def run_skill(name, args, env, log_path):
    skill_name, script_subpath, _ = SKILLS[name]
    script = SKILLS_DIR / skill_name / script_subpath
    if not script.exists():
        print(f"  ⚠ {name}: скрипт не найден ({script}). Пропуск.")
        return False, "not_installed"

    print(f"  ▶ {name} ({skill_name})...", flush=True)
    t0 = time.time()
    try:
        with open(log_path, "w") as logf:
            res = subprocess.run(
                ["python3", str(script), *args],
                env=env, timeout=900, stdout=logf, stderr=subprocess.STDOUT,
            )
        elapsed = time.time() - t0
        ok = res.returncode == 0
        marker = "✓" if ok else "✗"
        print(f"    {marker} {name} ({elapsed:.0f}s, exit {res.returncode})")
        return ok, "ok" if ok else f"exit_{res.returncode}"
    except subprocess.TimeoutExpired:
        print(f"    ✗ {name}: timeout 15min")
        return False, "timeout"
    except Exception as e:
        print(f"    ✗ {name}: {e}")
        return False, f"error: {e}"


def read_safe(path, max_lines=None):
    if not Path(path).exists():
        return ""
    txt = Path(path).read_text(encoding="utf-8")
    if max_lines:
        return "\n".join(txt.splitlines()[:max_lines])
    return txt


def short_summary(file_path, max_chars=600):
    """Берёт первые ~max_chars (после заголовка) из MD файла."""
    if not Path(file_path).exists():
        return ""
    txt = Path(file_path).read_text(encoding="utf-8")
    # Skip H1
    lines = txt.split("\n")
    body = []
    seen_header = False
    char_count = 0
    for line in lines:
        if line.startswith("# ") and not seen_header:
            seen_header = True
            continue
        body.append(line)
        char_count += len(line)
        if char_count > max_chars:
            break
    return "\n".join(body).strip()


def generate_suite_report(domain, completed_skills, args):
    """Собираем executive summary."""
    md = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    md.append(f"# Комплексний аудит `{domain}`\n")
    md.append(f"**Згенеровано:** {today}\n")
    md.append(f"**Запущено скілів:** {sum(1 for v in completed_skills.values() if v[0])} з {len(completed_skills)}\n")

    md.append("## 📋 Зведення (executive summary)\n")

    # 1. SEO + контентный аудит
    if completed_skills.get("audit", (False,))[0] and Path("REPORT.md").exists():
        md.append("### 🔍 SEO + контентний аудит ([REPORT.md](REPORT.md))\n")
        # Извлекаем секцию TL;DR через regex или просто берём топ-N
        report_txt = Path("REPORT.md").read_text(encoding="utf-8")
        # Ищем сводку
        m = re.search(r"## 📊 Сводка\n([\s\S]*?)\n## ", report_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")
        else:
            md.append(short_summary("REPORT.md", 400))
            md.append("")

    # 2. Sales report
    if completed_skills.get("sales", (False,))[0] and Path("SALES_REPORT.md").exists():
        md.append("### 💰 Продажі + ABC ([SALES_REPORT.md](SALES_REPORT.md))\n")
        sales_txt = Path("SALES_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📊 Сводка\n([\s\S]*?)\n## ", sales_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")

    # 3. Photo audit
    if completed_skills.get("photo", (False,))[0] and Path("PHOTO_REPORT.md").exists():
        md.append("### 📸 Аудит фото ([PHOTO_REPORT.md](PHOTO_REPORT.md))\n")
        photo_txt = Path("PHOTO_REPORT.md").read_text(encoding="utf-8")
        # Знахідки
        m = re.search(r"## 🚨 Знахідки\n([\s\S]*?)\n## ", photo_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")

    # 4. Text quality
    if completed_skills.get("text", (False,))[0] and Path("TEXT_QUALITY_REPORT.md").exists():
        md.append("### 📝 Якість текстів ([TEXT_QUALITY_REPORT.md](TEXT_QUALITY_REPORT.md))\n")
        text_txt = Path("TEXT_QUALITY_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📊 Зведення\n([\s\S]*?)\n## ", text_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")

    # 5. Consistency
    if completed_skills.get("consistency", (False,))[0] and Path("CONSISTENCY_REPORT.md").exists():
        md.append("### 🔍 Консистентність ([CONSISTENCY_REPORT.md](CONSISTENCY_REPORT.md))\n")
        cons_txt = Path("CONSISTENCY_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📋 Знахідки\n([\s\S]*?)\n## ", cons_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")
        elif "Конфліктів не знайдено" in cons_txt:
            md.append("Конфліктів не знайдено. ✅\n")

    # 6. Content gaps
    if completed_skills.get("gaps", (False,))[0] and Path("gaps.json").exists():
        gaps = json.loads(Path("gaps.json").read_text(encoding="utf-8"))
        md.append(f"### 📝 Пропуски в контенті ([gaps.json](gaps.json))\n")
        md.append(f"Товарів з пустими полями: **{len(gaps)}**.")
        if gaps:
            md.append("Запусти `horoshop-content-fill` для масового заповнення.")
        md.append("")

    # 7. Design system
    if completed_skills.get("design", (False,))[0] and Path("DESIGN_SYSTEM.md").exists():
        md.append("### 🎨 Дизайн-система ([DESIGN_SYSTEM.md](DESIGN_SYSTEM.md))\n")
        design_txt = Path("DESIGN_SYSTEM.md").read_text(encoding="utf-8")
        m = re.search(r"## 🎨 Топ-15 цветов[\s\S]*?\n([\s\S]*?)\n## ", design_txt)
        if m:
            md.append("Топ цветов и шрифтов извлечены — см. файл.\n")

    # ── Статус выполнения ─────────────────────────────────────────
    md.append("## 📦 Статус скілів\n")
    md.append("| Скіл | Статус | Звіт |")
    md.append("|---|---|---|")
    skill_files = {
        "audit": "REPORT.md",
        "sales": "SALES_REPORT.md",
        "gaps": "gaps.json",
        "photo": "PHOTO_REPORT.md",
        "text": "TEXT_QUALITY_REPORT.md",
        "consistency": "CONSISTENCY_REPORT.md",
        "design": "DESIGN_SYSTEM.md",
    }
    for name, (ok, status) in completed_skills.items():
        skill_full = SKILLS[name][0]
        marker = "✅" if ok else "❌"
        report = skill_files.get(name, "—")
        report_link = f"[{report}]({report})" if Path(report).exists() else "—"
        md.append(f"| `{skill_full}` | {marker} {status} | {report_link} |")
    md.append("")

    # ── Брендовый футер ───────────────────────────────────────────
    md.append("---\n")
    md.append("🛠 *Згенеровано скілом-комплексом [horoshop-suite](https://github.com/IgorShutko/horoshop-claude-skill) — створено агенцією [Target+](https://www.targetplus-agency.com/) (performance-маркетинг для UA e-commerce).*  ")
    md.append("*Допомога з впровадженням рекомендацій? [TG @shutko_ads](https://t.me/shutko_ads) або [заявка через сайт](https://www.targetplus-agency.com/).*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Horoshop Suite — orchestrator")
    parser.add_argument("--skip", default="", help="Пропустить скиллы (audit,sales,...)")
    parser.add_argument("--only", default="", help="Запустить только эти")
    parser.add_argument("--from", dest="date_from", default=None, help="Период для sales (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", default=None, help="Период для sales")
    parser.add_argument("--site-url", default=None, help="URL для design-extract")
    args = parser.parse_args()

    if not all([DOMAIN, LOGIN, PASSWORD]):
        print("ERROR: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD не заданы", file=sys.stderr)
        sys.exit(1)

    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    selected = list(SKILLS.keys())
    if only:
        selected = [s for s in selected if s in only]
    if skip:
        selected = [s for s in selected if s not in skip]

    print(f"=== Horoshop Suite — {DOMAIN} ===")
    print(f"Скіллов до запуска: {selected}\n")

    env = os.environ.copy()
    completed = {}
    Path("logs").mkdir(exist_ok=True)

    # Период для sales
    date_from = args.date_from or (datetime.now().date() - timedelta(days=30)).isoformat()
    date_to = args.date_to or datetime.now().date().isoformat()

    site_url = args.site_url or f"https://{DOMAIN}/"

    for name in selected:
        log_path = Path("logs") / f"{name}.log"
        if name == "audit":
            ok, status = run_skill(name, [], env, log_path)
        elif name == "sales":
            ok, status = run_skill(name, ["--from", date_from, "--to", date_to], env, log_path)
        elif name in ("gaps", "photo", "text", "consistency"):
            cat_path = "catalog.json"
            if Path(cat_path).exists():
                ok, status = run_skill(name, ["--from-file", cat_path], env, log_path)
            else:
                ok, status = run_skill(name, [], env, log_path)
        elif name == "design":
            ok, status = run_skill(name, ["--url", site_url], env, log_path)
        else:
            ok, status = False, "unknown"
        completed[name] = (ok, status)

    print("\n[+] Формирование SUITE_REPORT.md...")
    report = generate_suite_report(DOMAIN, completed, args)
    Path("SUITE_REPORT.md").write_text(report, encoding="utf-8")

    print(f"\n━━━ TL;DR ━━━")
    ok_count = sum(1 for v in completed.values() if v[0])
    print(f"  Запущено: {ok_count} / {len(completed)} скіллов")
    for name, (ok, status) in completed.items():
        marker = "✓" if ok else "✗"
        print(f"  {marker} {SKILLS[name][0]:30s} {status}")
    print(f"\nГолова: SUITE_REPORT.md")


if __name__ == "__main__":
    main()

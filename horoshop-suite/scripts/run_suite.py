#!/usr/bin/env python3
"""Horoshop Suite — оркестратор всех скиллов.

Использование:
  python3 run_suite.py [--skip photo,consistency]
                       [--only audit,sales]
                       [--from 2026-04-01 --to 2026-04-30]

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


def validate_artifact(skill_name):
    """Проверяет качество артефакта скилла. Возвращает (status, reason).

    status: 'ok' / 'partial' / 'missing'
    """
    artifact_map = {
        "audit": ("REPORT.md", _validate_audit_report),
        "sales": ("SALES_REPORT.md", _validate_md_with_sections),
        "gaps": ("gaps.json", _validate_gaps_json),
        "photo": ("PHOTO_REPORT.md", _validate_md_with_sections),
        "text": ("TEXT_QUALITY_REPORT.md", _validate_md_with_sections),
        "consistency": ("CONSISTENCY_REPORT.md", _validate_md_with_sections),
    }

    if skill_name not in artifact_map:
        return "ok", "unknown skill"

    fpath, validator = artifact_map[skill_name]
    if not Path(fpath).exists():
        return "missing", f"{fpath} не створений"

    return validator(fpath)


def _validate_audit_report(fpath):
    """REPORT.md — должен иметь >= 5 секций (## ...)."""
    txt = Path(fpath).read_text(encoding="utf-8")
    sections = re.findall(r"^## ", txt, re.MULTILINE)
    if len(sections) < 5:
        return "partial", f"тільки {len(sections)} секцій (< 5)"
    return "ok", f"{len(sections)} секцій"


def _validate_md_with_sections(fpath):
    """Любой *_REPORT.md — должна быть хоть одна секция и > 200 байт."""
    txt = Path(fpath).read_text(encoding="utf-8")
    if len(txt) < 200:
        return "partial", f"звіт занадто короткий ({len(txt)} байт)"
    sections = re.findall(r"^## ", txt, re.MULTILINE)
    if len(sections) < 1:
        return "partial", "немає секцій ##"
    return "ok", f"{len(sections)} секцій"


def _validate_gaps_json(fpath):
    """gaps.json — пустой [] валиден (=нет gaps). Главное — JSON парсится."""
    try:
        data = json.loads(Path(fpath).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return "ok", f"{len(data)} gaps"
        return "partial", "не-список JSON"
    except Exception as e:
        return "partial", f"невалідний JSON: {e}"


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


# Маппинг: имя скилла → файл артефакта (используется и в merge, и в статус-таблице)
SKILL_REPORT_FILES = {
    "audit": "REPORT.md",
    "sales": "SALES_REPORT.md",
    "gaps": "gaps.json",
    "photo": "PHOTO_REPORT.md",
    "text": "TEXT_QUALITY_REPORT.md",
    "consistency": "CONSISTENCY_REPORT.md",
}


def generate_suite_report(domain, completed_skills, args):
    """Собирает executive summary.

    Важно: проходит по ВСЕМ скиллам списка (не только по completed_skills),
    проверяя наличие соответствующих артефактов на диске.
    Это позволяет использовать --only audit,sales без перетирания
    summary остальных скиллов из предыдущих запусков.
    """
    md = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    md.append(f"# Комплексний аудит `{domain}`\n")
    md.append(f"**Згенеровано:** {today}\n")

    # Считаем сколько артефактов на диске (не только из текущего запуска)
    disk_artifacts = sum(1 for f in SKILL_REPORT_FILES.values() if Path(f).exists())
    md.append(f"**Артефактів на диску:** {disk_artifacts} / {len(SKILL_REPORT_FILES)}\n")

    md.append("## 📋 Зведення (executive summary)\n")

    # Хелпер: артефакт включается если файл на диске. Текущий запуск или нет — не важно.
    def has(skill_name):
        report_file = SKILL_REPORT_FILES.get(skill_name)
        return report_file and Path(report_file).exists()

    # 1. SEO + контентный аудит
    if has("audit"):
        md.append("### 🔍 SEO + контентний аудит ([REPORT.md](REPORT.md))\n")
        report_txt = Path("REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📊 Сводка\n([\s\S]*?)\n## ", report_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")
        else:
            md.append(short_summary("REPORT.md", 400))
            md.append("")

    # 2. Sales report
    if has("sales"):
        md.append("### 💰 Продажі + ABC ([SALES_REPORT.md](SALES_REPORT.md))\n")
        sales_txt = Path("SALES_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📊 Сводка\n([\s\S]*?)\n## ", sales_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")

    # 3. Photo audit
    if has("photo"):
        md.append("### 📸 Аудит фото ([PHOTO_REPORT.md](PHOTO_REPORT.md))\n")
        photo_txt = Path("PHOTO_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 🚨 Знахідки\n([\s\S]*?)\n## ", photo_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")

    # 4. Text quality
    if has("text"):
        md.append("### 📝 Якість текстів ([TEXT_QUALITY_REPORT.md](TEXT_QUALITY_REPORT.md))\n")
        text_txt = Path("TEXT_QUALITY_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📊 Зведення\n([\s\S]*?)\n## ", text_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")

    # 5. Consistency
    if has("consistency"):
        md.append("### 🔍 Консистентність ([CONSISTENCY_REPORT.md](CONSISTENCY_REPORT.md))\n")
        cons_txt = Path("CONSISTENCY_REPORT.md").read_text(encoding="utf-8")
        m = re.search(r"## 📋 Знахідки\n([\s\S]*?)\n## ", cons_txt)
        if m:
            md.append(m.group(1).strip())
            md.append("")
        elif "Конфліктів не знайдено" in cons_txt:
            md.append("Конфліктів не знайдено. ✅\n")

    # 6. Content gaps
    if has("gaps"):
        try:
            gaps = json.loads(Path("gaps.json").read_text(encoding="utf-8"))
            md.append(f"### 📝 Пропуски в контенті ([gaps.json](gaps.json))\n")
            md.append(f"Товарів з пустими полями: **{len(gaps)}**.")
            if gaps:
                md.append("Запусти `horoshop-content-fill` для масового заповнення.")
            md.append("")
        except Exception:
            pass

    # ── Статус виконання ─────────────────────────────────────────
    md.append("## 📦 Статус скілів\n")
    md.append("| Скіл | Останній запуск | Якість артефакту | Файл |")
    md.append("|---|---|---|---|")
    for name, full_skill_data in SKILLS.items():
        skill_full = full_skill_data[0]
        report = SKILL_REPORT_FILES.get(name, "—")
        report_exists = Path(report).exists() if report != "—" else False
        report_link = f"[{report}]({report})" if report_exists else "—"

        # Статус: если в текущем запуске — берём оттуда. Иначе — «з попереднього запуску» если артефакт есть.
        if name in completed_skills:
            ok, status = completed_skills[name]
            if "partial" in status or "missing" in status:
                run_marker = "⚠️"
            else:
                run_marker = "✅" if ok else "❌"
            run_status = f"{run_marker} {status} (зараз)"
        elif report_exists:
            run_status = "💾 з попереднього запуску"
        else:
            run_status = "— не запускався"

        # Качество артефакта на диске (актуальное состояние)
        if report_exists:
            art_status, art_reason = validate_artifact(name)
            if art_status == "ok":
                art_quality = f"✅ {art_reason}"
            elif art_status == "partial":
                art_quality = f"⚠️ {art_reason}"
            else:
                art_quality = f"❌ {art_reason}"
        else:
            art_quality = "—"

        md.append(f"| `{skill_full}` | {run_status} | {art_quality} | {report_link} |")
    md.append("")

    # ── Брендовый футер ───────────────────────────────────────────
    md.append("---\n")
    md.append("🛠 *Згенеровано скілом-комплексом [horoshop-suite](https://github.com/IgorShutko/horoshop-claude-skill) — створено агенцією [Target+](https://www.targetplus-agency.com/) (performance-маркетинг для UA e-commerce).*  ")
    md.append("*Допомога з впровадженням рекомендацій? [TG @shutko_ads](https://t.me/shutko_ads) або [заявка через сайт](https://www.targetplus-agency.com/).*")

    return "\n".join(md)


def preflight_check_dependencies():
    """Проверяет что Python-пакеты установлены, чтобы не запускать 7 скиллов с гарантированным провалом."""
    missing = []
    for mod in ("requests", "bs4", "lxml"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"\n❌ ERROR: відсутні Python-пакети: {', '.join(missing)}", file=sys.stderr)
        print("\nВстанови:", file=sys.stderr)
        print(f"  python3 -m pip install --user --break-system-packages {' '.join(missing)}", file=sys.stderr)
        print("\nПісля встановлення — повтори запуск.", file=sys.stderr)
        return False
    return True


def preflight_auth(domain, login, password):
    """Перевіряє авторизацію перед запуском 7 скилів — щоб не витрачати 5хв на гарантований fail."""
    import urllib.request
    import urllib.error

    url = f"https://{domain}/api/auth/"
    data = json.dumps({"login": login, "password": password}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read())
        if body.get("status") == "OK":
            return True, "OK"
        return False, body.get("response", {}).get("message", "невідома помилка")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"мережа: {e.reason}"
    except Exception as e:
        return False, f"помилка: {e}"


def main():
    parser = argparse.ArgumentParser(description="Horoshop Suite — orchestrator")
    parser.add_argument("--skip", default="", help="Пропустить скиллы (audit,sales,...)")
    parser.add_argument("--only", default="", help="Запустить только эти")
    parser.add_argument("--from", dest="date_from", default=None, help="Период для sales (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", default=None, help="Период для sales")
    parser.add_argument("--check-sizes", action="store_true",
                        help="Передать --check-sizes в photo-audit (HEAD-запросы, медленнее)")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Пропустить preflight (auth + deps). По умолчанию выполняется.")
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

    # ─── Preflight ──────────────────────────────────────────────────────
    if not args.skip_preflight:
        print("[preflight] Перевірка залежностей...")
        if not preflight_check_dependencies():
            sys.exit(1)
        print("  ✓ requests, bs4, lxml встановлено\n")

        print("[preflight] Перевірка auth...")
        ok, msg = preflight_auth(DOMAIN, LOGIN, PASSWORD)
        if not ok:
            print(f"  ❌ Auth fail: {msg}", file=sys.stderr)
            print(f"  Перевір логін/пароль API-юзера в {DOMAIN}/admin", file=sys.stderr)
            sys.exit(1)
        print(f"  ✓ Auth OK на {DOMAIN}\n")

    env = os.environ.copy()
    completed = {}
    Path("logs").mkdir(exist_ok=True)

    # Период для sales — предупреждаем если используется default
    if args.date_from or args.date_to:
        date_from = args.date_from or (datetime.now().date() - timedelta(days=30)).isoformat()
        date_to = args.date_to or datetime.now().date().isoformat()
    else:
        date_from = (datetime.now().date() - timedelta(days=30)).isoformat()
        date_to = datetime.now().date().isoformat()
        if "sales" in selected:
            print(f"⚠️  Період sales-report не вказаний — використовую default: {date_from} → {date_to} (30 днів).")
            print(f"   Для іншого періоду використай --from YYYY-MM-DD --to YYYY-MM-DD\n")

    # photo-audit: предупреждение про size check
    if "photo" in selected and not args.check_sizes:
        print("⚠️  photo-audit: --check-sizes ВИМКНЕНО (default).")
        print("   Скрипт порахує тільки кількість фото, не перевіряючи їх вагу.")
        print("   Для повного аудиту: передай --check-sizes (повільніше, ~1 HEAD-запит на товар).\n")

    for name in selected:
        log_path = Path("logs") / f"{name}.log"
        if name == "audit":
            ok, status = run_skill(name, [], env, log_path)
        elif name == "sales":
            ok, status = run_skill(name, ["--from", date_from, "--to", date_to], env, log_path)
        elif name in ("gaps", "text", "consistency"):
            cat_path = "catalog.json"
            if Path(cat_path).exists():
                ok, status = run_skill(name, ["--from-file", cat_path], env, log_path)
            else:
                ok, status = run_skill(name, [], env, log_path)
        elif name == "photo":
            cat_path = "catalog.json"
            extra = ["--check-sizes"] if args.check_sizes else []
            if Path(cat_path).exists():
                ok, status = run_skill(name, ["--from-file", cat_path] + extra, env, log_path)
            else:
                ok, status = run_skill(name, extra, env, log_path)
        else:
            ok, status = False, "unknown"

        # Валидация артефакта (даже если returncode == 0, артефакт может быть пустой)
        if ok:
            artifact_status, artifact_reason = validate_artifact(name)
            if artifact_status == "partial":
                ok = False  # формально не fail, но в SUITE_REPORT отразится
                status = f"partial: {artifact_reason}"
                print(f"    ⚠️ {name} (artifact) {artifact_reason}")
            elif artifact_status == "missing":
                ok = False
                status = f"missing: {artifact_reason}"
                print(f"    ✗ {name} (artifact) {artifact_reason}")

        completed[name] = (ok, status)

    print("\n[+] Формирование SUITE_REPORT.md...")
    report = generate_suite_report(DOMAIN, completed, args)
    Path("SUITE_REPORT.md").write_text(report, encoding="utf-8")

    # Структурированный статус для постпроцессинга
    suite_status = {
        "domain": DOMAIN,
        "timestamp": datetime.now().isoformat(),
        "selected": selected,
        "results": {name: {"ok": ok, "status": status} for name, (ok, status) in completed.items()},
        "args": {
            "from": args.date_from,
            "to": args.date_to,
            "check_sizes": args.check_sizes,
            "skip": args.skip,
            "only": args.only,
        },
    }
    Path("suite_status.json").write_text(json.dumps(suite_status, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n━━━ TL;DR ━━━")
    ok_list, partial_list, failed_list = [], [], []
    for name, (ok, status) in completed.items():
        if ok:
            ok_list.append(name)
        elif "partial" in status:
            partial_list.append(name)
        else:
            failed_list.append(name)

    print(f"  ✅ ОК: {len(ok_list)} · ⚠️  Partial: {len(partial_list)} · ❌ Fail: {len(failed_list)} (з {len(completed)})\n")
    for name, (ok, status) in completed.items():
        if ok:
            marker = "✅"
        elif "partial" in status:
            marker = "⚠️"
        else:
            marker = "❌"
        print(f"  {marker} {SKILLS[name][0]:30s} {status}")
    print(f"\nГолова: SUITE_REPORT.md  ·  суддя: suite_status.json")

    # Exit code: 0 если все ок (без partial), 1 если хотя бы partial/fail
    sys.exit(0 if (len(partial_list) == 0 and len(failed_list) == 0) else 1)


if __name__ == "__main__":
    main()

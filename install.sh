#!/usr/bin/env bash
# Установка всех скиллов horoshop-claude-skill для Claude Code
# Использование: curl -fsSL https://raw.githubusercontent.com/IgorShutko/horoshop-claude-skill/main/install.sh | bash

set -e

REPO="https://github.com/IgorShutko/horoshop-claude-skill.git"
SKILLS_ROOT="$HOME/.claude/skills"

SKILLS=(
  "horoshop-full-audit"
  "horoshop-sales-report"
  "horoshop-content-fill"
  "horoshop-photo-audit"
  "horoshop-text-quality"
  "horoshop-consistency"
  "horoshop-design-extract"
  "horoshop-marketing-psych"
  "horoshop-suite"
)

echo "→ Установка ${#SKILLS[@]} скіллов horoshop-claude-skill..."

# Проверка зависимостей системы
command -v python3 >/dev/null || { echo "ERROR: Python 3 не найден"; exit 1; }
command -v git >/dev/null || { echo "ERROR: git не найден"; exit 1; }

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  python3 → ${PYTHON_VERSION}"

# Клонируем во временную папку
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT
git clone --depth 1 "$REPO" "$TMP/repo" 2>&1 | tail -3

# Копируем каждый скилл в ~/.claude/skills/<name>/
mkdir -p "$SKILLS_ROOT"
for skill in "${SKILLS[@]}"; do
  src="$TMP/repo/$skill"
  if [ ! -d "$src" ]; then
    echo "  ⚠ $skill: не найден в репо, пропуск"
    continue
  fi
  dst="$SKILLS_ROOT/$skill"
  mkdir -p "$dst"
  cp -r "$src/"* "$dst/"
  if [ -d "$dst/scripts" ]; then
    chmod +x "$dst/scripts/"*.py 2>/dev/null || true
  fi
  echo "  ✓ $skill → $dst"
done

# ─── Установка Python-зависимостей ─────────────────────────────────────────
echo ""
echo "→ Установка Python-зависимостей..."

# Все нужные пакеты (объединённые requirements всех скиллов)
PYTHON_DEPS="requests beautifulsoup4 lxml"

# macOS Homebrew Python требует --break-system-packages (PEP 668)
PIP_FLAGS="--user"
if python3 -m pip install --help 2>&1 | grep -q break-system-packages; then
  PIP_FLAGS="$PIP_FLAGS --break-system-packages"
fi

if ! python3 -m pip install $PIP_FLAGS $PYTHON_DEPS; then
  echo ""
  echo "❌ ERROR: pip install провалился."
  echo ""
  echo "Попробуй вручную:"
  echo "  python3 -m pip install --user --break-system-packages $PYTHON_DEPS"
  echo ""
  echo "Или через venv (рекомендую для macOS):"
  echo "  python3 -m venv ~/.claude/skills/.horoshop-venv"
  echo "  source ~/.claude/skills/.horoshop-venv/bin/activate"
  echo "  pip install $PYTHON_DEPS"
  exit 1
fi

# ─── Верификация: пакеты реально импортируются ─────────────────────────────
echo ""
echo "→ Проверка установки..."
VERIFY_OUTPUT=$(python3 -c "
import sys
errors = []
try:
    import requests
    print(f'  ✓ requests {requests.__version__}')
except ImportError as e:
    errors.append(('requests', str(e)))
try:
    import bs4
    print(f'  ✓ beautifulsoup4 {bs4.__version__}')
except ImportError as e:
    errors.append(('beautifulsoup4', str(e)))
try:
    import lxml
    print(f'  ✓ lxml {lxml.__version__}')
except ImportError as e:
    errors.append(('lxml', str(e)))

if errors:
    print('ERROR:')
    for name, err in errors:
        print(f'  ✗ {name}: {err}')
    sys.exit(1)
" 2>&1)
VERIFY_CODE=$?

echo "$VERIFY_OUTPUT"

if [ $VERIFY_CODE -ne 0 ]; then
  echo ""
  echo "❌ Зависимости установились, но не импортируются."
  echo "   Это может быть mismatch между python3 и pip."
  echo ""
  echo "Проверь какой python3 использует Claude Code:"
  echo "  which python3"
  echo "  python3 -m pip show requests"
  echo ""
  echo "Если установка прошла в другую среду — установи вручную в ту,"
  echo "которая будет использоваться скиллами."
  exit 1
fi

# ─── Финал ─────────────────────────────────────────────────────────────────
echo ""
echo "✅ Установлено ${#SKILLS[@]} скіллов в: $SKILLS_ROOT"
echo "✅ Зависимости проверены: requests, beautifulsoup4, lxml"
echo ""
echo "Используй в любом чате Claude Code:"
echo '  "Полный аудит магазина на хорошопе example.com.ua"      → horoshop-suite'
echo '  "Сделай аудит магазина на хорошопе example.com.ua"      → horoshop-full-audit'
echo '  "Отчёт по продажам за месяц"                            → horoshop-sales-report'
echo '  "Заполни пустые описания товаров"                       → horoshop-content-fill'
echo ""

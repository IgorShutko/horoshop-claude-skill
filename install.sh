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

echo "→ Установка ${#SKILLS[@]} скиллов horoshop-claude-skill..."

# Проверка зависимостей
command -v python3 >/dev/null || { echo "ERROR: Python 3 не найден"; exit 1; }
command -v git >/dev/null || { echo "ERROR: git не найден"; exit 1; }

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

echo ""
echo "→ Установка Python-зависимостей..."
PIP_FLAGS="--user --quiet"
# macOS Homebrew Python требует --break-system-packages
if python3 -m pip install --help 2>&1 | grep -q break-system-packages; then
  PIP_FLAGS="$PIP_FLAGS --break-system-packages"
fi
python3 -m pip install $PIP_FLAGS requests beautifulsoup4 lxml || {
  echo "WARN: автоматическая установка зависимостей не прошла."
  echo "      Установи вручную: pip install requests beautifulsoup4 lxml"
}

echo ""
echo "✅ Установлено ${#SKILLS[@]} скиллов в: $SKILLS_ROOT"
echo ""
echo "Используй в любом чате Claude Code:"
echo '  "Полный аудит магазина на хорошопе example.com.ua"      → horoshop-suite'
echo '  "Сделай аудит магазина на хорошопе example.com.ua"      → horoshop-full-audit'
echo '  "Отчёт по продажам за месяц"                            → horoshop-sales-report'
echo '  "Заполни пустые описания товаров"                       → horoshop-content-fill'
echo ""

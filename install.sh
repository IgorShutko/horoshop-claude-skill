#!/usr/bin/env bash
# Установка horoshop-full-audit skill для Claude Code
# Использование: curl -fsSL https://raw.githubusercontent.com/<USER>/horoshop-claude-skill/main/install.sh | bash

set -e

SKILL_NAME="horoshop-full-audit"
TARGET_DIR="$HOME/.claude/skills/$SKILL_NAME"
REPO="https://github.com/<YOUR_USERNAME>/horoshop-claude-skill.git"  # ← поменять на свой URL

echo "→ Установка $SKILL_NAME..."

# Проверка зависимостей
command -v python3 >/dev/null || { echo "ERROR: Python 3 не найден"; exit 1; }
command -v git >/dev/null || { echo "ERROR: git не найден"; exit 1; }

# Клонируем во временную папку
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT
git clone --depth 1 "$REPO" "$TMP/repo" 2>&1 | tail -3

# Копируем содержимое в ~/.claude/skills/horoshop-full-audit
mkdir -p "$TARGET_DIR"
cp -r "$TMP/repo/SKILL.md" "$TMP/repo/scripts" "$TMP/repo/references" "$TMP/repo/evals" "$TARGET_DIR/"
chmod +x "$TARGET_DIR/scripts/"*.py

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
echo "✅ Скилл установлен в: $TARGET_DIR"
echo ""
echo "Используй в любом чате Claude Code:"
echo '  "Сделай аудит магазина на хорошопе example.com.ua"'
echo ""

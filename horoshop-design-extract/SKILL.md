---
name: horoshop-design-extract
description: Извлечение дизайн-системы магазина на Хорошопе — цвета, шрифты, логотипы. Используй ВСЕГДА когда пользователь просит "выгрузи дизайн магазина", "получи бренд-цвета", "вытащи логотип", "узнай какие шрифты на сайте", "design system from shop". Скилл парсит публичный HTML+CSS магазина, извлекает доминирующие цвета (из CSS variables и frequency analysis), главные шрифты (font-family), логотип (header img), favicon. Сохраняет в `design.json` + скачивает logo/favicon в `assets/`. Не требует API-ключа.
---

# Horoshop Design Extract

Выгрузка дизайн-системы магазина: цвета, шрифты, логотип.

## Когда применять

- «Выгрузи дизайн-систему»
- «Получи цвета магазина»
- «Скачай логотип»
- «Узнай шрифты сайта»
- Перед использованием `horoshop-content-fill` для генерации описаний в стиле бренда (используется в HTML с inline-стилями)

## Что извлекает

| Артефакт | Источник | Output |
|---|---|---|
| Цвета | CSS variables (`--primary`, `--accent`), inline styles, frequency analysis | `design.json: colors[]` |
| Шрифты | `font-family` в CSS | `design.json: fonts[]` |
| Логотип | `<img>` в header, `og:image` | `assets/logo.png` или ссылка |
| Favicon | `<link rel="icon">` | `assets/favicon.*` |
| Viewport / lang | `<meta>`, `<html>` | `design.json: meta` |

## Pipeline

```
[1] GET https://<DOMAIN>/  (с whitelisted UA)
[2] Парсинг HTML: <link rel="stylesheet"> URLs, inline <style>
[3] GET всех CSS файлов
[4] Извлечение цветов (CSS variables + hex/rgb регексами)
[5] Извлечение fонтов (font-family)
[6] Скачивание лого + favicon
[7] design.json + DESIGN_SYSTEM.md
```

## Использование

```bash
mkdir -p design_<domain>
cd design_<domain>
python3 ${SKILL_DIR}/scripts/extract.py --url https://example.com.ua
```

Опции:
- `--url` — полный URL главной (обязательно)
- `--max-css 5` — максимум CSS файлов скачивать (default 5)
- `--no-download` — не скачивать ассеты, только URL'ы

## Output

- `design.json` — структурированная дизайн-система
- `DESIGN_SYSTEM.md` — markdown-обзор с превью
- `assets/logo.png` (если найден)
- `assets/favicon.ico` (если найден)
- `assets/main.css` — копия главного CSS (для офлайн)

## Что НЕ делает

- ❌ Не реверсит Figma — это извлечение **с прода**, не реконструкция дизайна
- ❌ Не парсит JS-рендереные элементы (Хорошоп статичен — это и не нужно)
- ❌ Не предлагает редизайн — только сбор того что есть
- ❌ Не работает с приватными CSS (за CDN с auth)

## Полезно

После extract — данные можно использовать в:
- `horoshop-content-fill` — генерация описаний с inline-стилями в брендовых цветах
- Презентации клиенту: «вот ваша текущая визуальная система»
- Перед редизайном — фиксация старого

## Refs

- `references/horoshop_help.md` — выжимка из справки Хорошопа: типы логотипов (4 варианта), стили стикеров, темы, Редактор дизайна. **Цитируй её в DESIGN_SYSTEM.md со ссылками на источник.**

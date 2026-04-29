# Horoshop API — что важно для аудита и фиксов

## Auth

```
POST https://<DOMAIN>/api/auth/
Content-Type: application/json

{"login":"<LOGIN>","password":"<PASSWORD>"}
```

Возвращает `token` на 600 сек. Передавать во всех последующих POST'ах.

## Endpoints, что используются в аудите

| Endpoint | Назначение |
|---|---|
| `catalog/export` | Полная выгрузка товаров с пагинацией (`offset`, `limit` до 100). Поддерживает `includedParams`/`excludedParams` |
| `pages/export` | Список категорий по `parent` (рекурсивно — обходим всё дерево) |
| `catalog/import` | Обновление товаров пакетно (до 50 за раз). Этот endpoint используется для ВСЕХ API-фиксов |

Из остальных endpoints (`hooks`, `currencies`, `delivery`, `payment`, `orders`, `users`, `b2b`) для аудита **ничего не нужно**.

## Поля товара, которые мы можем редактировать через `catalog/import`

| Поле | Тип | Заметки |
|---|---|---|
| `article` | str | **обязательно для идентификации товара** |
| `title.<lang>` | str | Название |
| `description.<lang>` | str (HTML) | Описание |
| `short_description.<lang>` | str (HTML) | Короткое описание |
| `seo_title.<lang>` | str | SEO title (≤70) |
| `seo_description.<lang>` | str | SEO description (120-160) |
| `seo_keywords.<lang>` | str | SEO keywords |
| `h1_title.<lang>` | str | H1 |
| `mod_title.<lang>` | str | Название модификации (для дочерних товаров) |
| `slug` | str | Только если `forceAliasUpdate: true` |
| `display_in_showcase` | bool | Показывать на сайте |
| `presence` | str | "В наявності" / "Немає" / "Очікується" |
| `price`, `price_old`, `discount` | num | Цены |
| `gtin`, `mpn` | str | Штрихкод и код производителя |
| `popularity` | int | Популярность |
| `icons[]` | str array | Стикеры по названию |
| `images.links[]` | url array | Картинки модификации |
| `gallery_common.links[]` | url array | Общие картинки |
| `gallery_360.links[]` | url array | 360-обзор |
| `parent.id` | int | ID основного раздела |
| `alt_parent[]` | path/id array | Доп. разделы |
| `accessories[]` | array | Аксессуары (по артикулу или категории) |
| `gifts[]` | array | Подарки |
| `characteristics.<key>` | dict | Характеристики (ключи кастомные у каждого магазина) |
| `countdown_end_time` | datetime | "YYYY-MM-DD HH:MM:SS" — таймер акции |
| `countdown_description.<lang>` | str | Описание акции под таймером |
| `installments_payment.id` | int | ПриватБанк: 1=выкл, 2=по умолч, 3+=N платежей |
| `monobank_installments_payment.id` | int | Monobank: аналогично |
| `unit_of_measurement.id` | int | Единица измерения |
| `wholesale_prices[]` | array | Оптовые цены (B2B) |
| `multiplicity`, `minimal_order` | int | Кратность и мин. заказ |
| `export_to_marketplace` | str (`;`-sep) | Маркетплейсы для выгрузки |
| `condition.id` | int | Состояние (Новый/БУ) |

## Поля, которые НЕ редактируются через API

| Поле | Где править |
|---|---|
| SEO-шаблоны категорий | Маркетинг → SEO → Шаблони |
| SEO-поля категорий | Каталог → Категорія (вручную) |
| SEO-текст категорий | Каталог → Категорія → SEO-текст |
| robots.txt | Только через поддержку Хорошопа |
| Sitemap.xml | Генерируется автоматически платформой |
| URL-формулы | Только через поддержку |
| Микроразметка/Schema | Реализована платформой |
| УКТ ВЕД (`uktzed`) | Возвращается через API, **но импортом не пишется** — только админка вручную |

## Pages API — нюанс

`pages/export` даёт только `id`, `parent`, `title`. **SEO-поля категорий через API недоступны.** Для аудита SEO категорий — только HTML-парсинг публичных страниц.

## Рекомендуемые batch-размеры

- Export: 100 товаров за запрос
- Import: 50 товаров за запрос (больше — растёт риск таймаута)
- Token: переавторизовываться каждые 550 секунд (TTL 600)

## User-Agent для HTML-парсинга

Хорошоп возвращает JS-challenge на некоторые UA. Проверено: **`Mozilla/5.0 (Horoshop SEO Audit)`** проходит без challenge. Не использовать дефолтный `python-requests/...` — получишь 518-байтовый JS stub.

## Коды ответа `catalog/import`

| Код | Что значит |
|---|---|
| 0 | Товар обновлён |
| 6 | Title обязателен (для нового товара) |
| 11 | Передано поле, которого нет в шаблоне «Каталог» — **частая причина silent fail** |
| 13 | Дубль ссылки |
| 22 | Изображение загружено |
| 26 | Ошибка загрузки изображения |

Если получаешь код 11 при импорте кастомных полей (например `installments_payment`) — значит в админке клиента эта функция не подключена. Передай пользователю фразу: «Чтобы поле `<X>` работало через API — включите его в `Налаштування → Система → Каталог → Шаблон даних`».

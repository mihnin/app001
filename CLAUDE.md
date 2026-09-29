# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

Учебное веб-приложение предзаказа напитков «Skuratov Coffee» (одна демо-точка). Источник требований —
`docs/*.docx`: бизнес-постановка v2.0 (БТ-01…07) и ТЗ v0.1 (ФТ-01…16, приёмочные испытания ПИ-01…12).
Код и тесты ссылаются на эти коды в docstring'ах. Принятые решения по открытым вопросам ТЗ — в `docs/STACK.md`.
Общайся с пользователем и пиши тексты интерфейса и сообщения ошибок на русском.

## Правила проекта (заданы пользователем)

- Только Python-стек (FastAPI + SQLite + статический HTML/CSS/Vanilla JS, без сборщиков фронтенда).
- Модульная структура, **не более 500 строк в любом файле**.
- Разработка через тесты: сначала тест (красный), затем код (зелёный), по слоям.

Файл `CLAUDE.md` на рабочем столе (студия браузерных игр, один `index.html`) к этому проекту не относится.

## Команды

```bash
pip install -r requirements.txt
python -m pytest                                   # все тесты (pytest.ini: testpaths=tests, -q)
python -m pytest tests/unit/test_cart.py           # один файл
python -m pytest tests/services/test_order_placement.py::test_concurrent_last_capacity  # один тест
python -m app.cli run [--port 8000]                # гость: /, сотрудник: /staff (пароль barista)
python -m app.cli reset --yes                      # сброс демо-данных (единственный способ сброса)
```

Окружение: `APP_DB` (по умолчанию `data/app.db`), `STAFF_PASSWORD`, `APP_TZ` (`Europe/Moscow`),
`APP_NOW="2026-09-29T10:00"` — тестовое время для ручной проверки вне часов 09:00–21:00.
Линтера в проекте нет.

## Архитектура

Слои зависят только вниз: `api → services → domain`, `services → db`.

- `app/domain/` — чистые функции без БД/HTTP: переходы статусов (`statuses.py`), разбор и цена корзины
  (`cart.py`), сетка интервалов и часы приёма (`slots.py`), пожелание (`wish.py`), сводка (`summary.py`).
  Ошибки — иерархия `DomainError` в `errors.py` (validation/forbidden/not_found/conflict/unavailable);
  `app/api/errors.py` отображает `kind` в HTTP 422/403/404/409/503 и единый JSON
  `{"error": {kind, code, message, details}}`. Фронтенд различает ошибки по `code`
  (`conditions_changed`, `slot_full`, `stale`, `attempt_reused`, …).
- `app/services/` — сценарии поверх `Context(db, clock, profile)`. Любая запись идёт через
  `Database.transaction()` (`BEGIN IMMEDIATE`), которая сериализует писателей и превращает `sqlite3.Error`
  в `UnavailableError`. На этом держатся ключевые гарантии ТЗ:
  - приём заказа (`order_service.place_order`) — одна транзакция: проверка повторной попытки → часы/пауза →
    цены/стоп-лист → интервал → сверка `expected_total` → резерв ёмкости (`slot_service.reserve`) → вставки;
  - идемпотентность: клиент шлёт `attempt_id`; таблица `attempts` хранит отпечаток содержимого
    (`cart.fingerprint`), повтор возвращает тот же заказ (HTTP 200 вместо 201);
  - команды сотрудника передают `expected_status`; несовпадение → `ConflictError(code="stale")` с актуальной карточкой;
  - ёмкость интервала считается в напитках, освобождается только при отмене из «Принят» (`releases_capacity`);
  - первые отметки времени (`preparing_at`, `ready_at`, `finished_at`) не перезаписываются (`COALESCE`).
- `orders_repo.to_card` строит одну и ту же карточку заказа для гостя и сотрудника (требование «одинаковые условия»).
- Время: единственный источник — серверные часы (`app/clock.py`: `SystemClock`, `OffsetClock` для `APP_NOW`,
  `FixedClock` для тестов). В БД — ISO UTC; «день» заказа — местная дата точки. Фронтенд синхронизирует
  смещение через `now` из `/api/point` (`syncServerTime`/`serverNow` в `common.js`) и не использует часы устройства.
- Доступ: гость идентифицируется случайным токеном в HttpOnly cookie `guest_token`, в БД хранится только
  SHA-256 (`guest_hash`). Чужой заказ → 404. Сотрудник — cookie `staff_token` + таблица `staff_sessions`;
  маршруты из `staff_routes.router` защищены зависимостью `require_staff`, вход/выход — в `staff_routes.public`.
  Публичного эндпоинта сброса быть не должно (это проверяет тест).
- Цены — целые копейки везде (БД, API, JS `money()`).
- `app/main.py:create_app(settings, clock)` — фабрика приложения. При старте вызывает `ensure_demo`;
  выставляет CSP `default-src 'self'` без `unsafe-inline`, поэтому в HTML нельзя inline-скрипты и атрибуты `style`.
  Весь пользовательский текст в JS выводится через `textContent` (хелпер `h()` в `common.js`).

## Тесты

- `tests/conftest.py` — фикстура `ctx`: свежая SQLite во `tmp_path` + `reset_demo` + `FixedClock` на 10:00 МСК
  29.09.2026; `tests/factories.py:msk(hh, mm)` задаёт местное время. Демо-меню из `app/db/seed.py` используется
  в тестах по id (`latte`, `espresso`, `oat`, …) — меняя seed, проверяй ожидаемые суммы в тестах.
- `tests/api/conftest.py` — отдельные `TestClient` для двух гостей и залогиненного сотрудника (пароль `secret-pass`).
- Отказ сохранения имитируется подменой `order_service._insert_event` через monkeypatch.

## Подводные камни

- В FastAPI возвращай dict и меняй `response.status_code`, а не `JSONResponse`: иначе теряется `Set-Cookie`
  гостевого токена, который выставляет зависимость `guest_id`.
- Тела запросов принимаются как сырой `dict`; строгая проверка типов (например, `qty` — int, но не bool/str)
  выполняется в домене, а не в Pydantic.
- В CSS есть `[hidden] { display: none !important; }`: без него классы с `display:flex` перебивают атрибут `hidden`.

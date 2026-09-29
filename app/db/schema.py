"""Схема SQLite. Все моменты времени — ISO 8601 в UTC; цены — целые копейки."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS point (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    address  TEXT NOT NULL,
    paused   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS addons (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    price     INTEGER NOT NULL CHECK (price >= 0),
    available INTEGER NOT NULL DEFAULT 1,
    sort      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS drinks (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL,
    sizes_json     TEXT NOT NULL,
    addon_ids_json TEXT NOT NULL,
    available      INTEGER NOT NULL DEFAULT 1,
    recommendation TEXT NOT NULL DEFAULT '',
    sort           INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS slot_limits (
    day   TEXT NOT NULL,
    start TEXT NOT NULL,
    lim   INTEGER NOT NULL CHECK (lim >= 0),
    used  INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
    PRIMARY KEY (day, start)
);
CREATE TABLE IF NOT EXISTS staff_sessions (
    token_hash TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id            TEXT PRIMARY KEY,
    number        TEXT NOT NULL,
    day           TEXT NOT NULL,
    guest_hash    TEXT NOT NULL,
    attempt_id    TEXT NOT NULL UNIQUE,
    point_name    TEXT NOT NULL,
    point_address TEXT NOT NULL,
    slot_key      TEXT NOT NULL,
    slot_start    TEXT NOT NULL,
    slot_end      TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN
                  ('accepted','preparing','ready','issued','cancelled','not_received')),
    total         INTEGER NOT NULL CHECK (total >= 0),
    wish          TEXT NOT NULL DEFAULT '',
    accepted_at   TEXT NOT NULL,
    preparing_at  TEXT,
    ready_at      TEXT,
    finished_at   TEXT,
    cancelled_by  TEXT,
    cancel_reason TEXT,
    UNIQUE (day, number)
);
CREATE INDEX IF NOT EXISTS ix_orders_guest ON orders (guest_hash);
CREATE INDEX IF NOT EXISTS ix_orders_day ON orders (day, slot_start, accepted_at);
CREATE TABLE IF NOT EXISTS order_lines (
    order_id    TEXT NOT NULL REFERENCES orders (id),
    pos         INTEGER NOT NULL,
    drink_id    TEXT NOT NULL,
    drink_name  TEXT NOT NULL,
    size        TEXT NOT NULL,
    addons_json TEXT NOT NULL,
    unit_price  INTEGER NOT NULL CHECK (unit_price >= 0),
    qty         INTEGER NOT NULL CHECK (qty > 0),
    line_total  INTEGER NOT NULL CHECK (line_total >= 0),
    PRIMARY KEY (order_id, pos)
);
CREATE TABLE IF NOT EXISTS attempts (
    id          TEXT PRIMARY KEY,
    guest_hash  TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    order_id    TEXT NOT NULL REFERENCES orders (id),
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT NOT NULL REFERENCES orders (id),
    prev_status TEXT,
    new_status  TEXT NOT NULL,
    at          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    reason      TEXT
);
"""

DATA_TABLES = ("events", "attempts", "order_lines", "orders", "slot_limits",
               "staff_sessions", "drinks", "addons", "point")
